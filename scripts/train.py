#!/usr/bin/env python3

"""
Script de entrenamiento para el MVP
"""

import os
import sys
import numpy as np
import pandas as pd
from datetime import datetime, timedelta

# Agregar src al path
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'src'))

from utils.config import Config
from utils.logging import setup_logger
from data.prometheus_client import PrometheusClient
from data.preprocessor import DataPreprocessor
from data.windowing import WindowGenerator
from models.lstm_autoencoder import LSTMAutoencoder

def generate_synthetic_data() -> pd.DataFrame:
    """
    Genera datos sintéticos para desarrollo
    """
    start_time = datetime.now() - timedelta(days=7)
    timestamps = pd.date_range(start=start_time, periods=20160, freq='30s')
    
    np.random.seed(42)
    n_points = len(timestamps)
     
    # Patrón base con ciclo diario
    hours = np.array([ts.hour for ts in timestamps])
    daily_pattern = 0.5 + 0.3 * np.sin(2 * np.pi * hours / 24)
    
    data = {
        'timestamp': timestamps,
        'request_rate': daily_pattern * 1000 + np.random.normal(0, 50, n_points),
        'latency_p95': daily_pattern * 200 + 100 + np.random.normal(0, 20, n_points),
        'memory_usage': daily_pattern * 0.7 + 0.3 + np.random.normal(0, 0.05, n_points),
        'error_rate': np.random.exponential(0.01, n_points),
        'cpu_usage': daily_pattern * 0.8 + 0.2 + np.random.normal(0, 0.1, n_points)
    }
    
    # Asegurar valores positivos
    for col in ['request_rate', 'latency_p95', 'error_rate']:
        data[col] = np.maximum(data[col], 0)
    
    data['memory_usage'] = np.clip(data['memory_usage'], 0, 1)
    data['cpu_usage'] = np.clip(data['cpu_usage'], 0, 1)
    
    return pd.DataFrame(data)

def main():
    """
    Pipeline completo de entrenamiento para MVP
    """
    logger = setup_logger()
    logger.info("=== Iniciando entrenamiento MVP ===")
    
    config = Config()
    
    # 1. Recopilar datos
    logger.info("Recopilando datos...")
    
    prometheus_url = config.get('data.prometheus_url')
    if prometheus_url:
        client = PrometheusClient(prometheus_url)
        df = client.get_tv_metrics(hours_back=24*7)
    else:
        logger.warning("No Prometheus URL configured, generating synthetic data")
        df = generate_synthetic_data()
    
    if df.empty:
        logger.error("No data available for training")
        return
    
    logger.info(f"Data shape: {df.shape}")
    
    # 2. Preprocesamiento
    logger.info("Preprocessing data...")
    preprocessor = DataPreprocessor(scaler_type='standard')
    df_processed = preprocessor.fit_transform(df)
    
    os.makedirs('models/', exist_ok=True)
    preprocessor.save_scaler('models/preprocessor.joblib')
    
    # 3. Crear ventanas deslizantes
    logger.info("Creating sliding windows...")
    window_size = config.get('windowing.window_size', 20)
    stride = config.get('windowing.stride', 20)
    
    windower = WindowGenerator(window_size=window_size, stride=stride)
    X, y = windower.create_sequences(df_processed)
    
    logger.info(f"Generated {X.shape[0]} sequences of shape {X.shape[1:]}")
    
    # 4. Split train/validation
    split_idx = int(0.8 * len(X))
    X_train, X_val = X[:split_idx], X[split_idx:]
    
    logger.info(f"Training samples: {X_train.shape[0]}, Validation samples: {X_val.shape[0]}")
    
    # 5. Entrenar modelo
    logger.info("Training LSTM Autoencoder...")
    
    input_shape = (X_train.shape[1], X_train.shape[2])
    encoder_layers = config.get('model.encoder_layers', [64, 32, 16])
    decoder_layers = config.get('model.decoder_layers', [16, 32, 64])
    
    model = LSTMAutoencoder(
        input_shape=input_shape,
        encoder_layers=encoder_layers,
        decoder_layers=decoder_layers
    )
    
    epochs = config.get('model.epochs', 50)
    batch_size = config.get('model.batch_size', 32)
    
    history = model.train(
        X_train=X_train,
        X_val=X_val,
        epochs=epochs,
        batch_size=batch_size
    )
    
    # 6. Guardar modelo
    model.save('models/lstm_autoencoder.h5')
    logger.info("Model saved to models/lstm_autoencoder.h5")
    
    # 7. Calcular threshold
    logger.info("Computing anomaly threshold...")
    reconstruction_errors = model.compute_reconstruction_error(X_val)
    
    threshold_method = config.get('alerting.threshold.method', 'percentile')
    if threshold_method == 'percentile':
        percentile = config.get('alerting.threshold.percentile', 95)
        threshold = np.percentile(reconstruction_errors, percentile)
    else:
        threshold = reconstruction_errors.mean() + 2 * reconstruction_errors.std()
    
    np.save('models/anomaly_threshold.npy', threshold)
    logger.info(f"Anomaly threshold: {threshold:.4f}")
    
    # 8. Estadísticas finales
    final_loss = history['loss'][-1]
    final_val_loss = history['val_loss'][-1] if 'val_loss' in history else None
    
    logger.info(f"Final training loss: {final_loss:.4f}")
    if final_val_loss:
        logger.info(f"Final validation loss: {final_val_loss:.4f}")
    
    logger.info("=== Entrenamiento completado ===")

if __name__ == "__main__":
    main()
