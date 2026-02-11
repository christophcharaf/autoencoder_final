#!/usr/bin/env python3
"""
Training Script for LSTM Autoencoder Anomaly Detection

This script trains an LSTM autoencoder model for detecting anomalies in TV-over-IP
service metrics. It supports both real data from Prometheus and synthetic data
for development/testing.

Configuration is loaded from YAML files in the config/ directory:
    - data.yaml: Data collection and preprocessing settings
    - model.yaml: Model architecture and training hyperparameters  
    - alerting.yaml: Threshold calculation settings
    - windowing.yaml: Sliding window configuration

Outputs:
    - models/lstm_autoencoder.weights.h5: Trained model weights
    - models/lstm_autoencoder_config.json: Model architecture config
    - models/preprocessor.joblib: Fitted data preprocessor/scaler
    - models/anomaly_threshold.npy: Computed anomaly threshold

Usage:
    python scripts/train.py

Author: Ing. Christopher Charaf
"""

import os
import sys
import numpy as np
import pandas as pd
from datetime import datetime, timedelta

# Add src directory to Python path for imports
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'src'))

from utils.config import Config
from utils.logging import setup_logger
from data.prometheus_client import PrometheusClient
from data.preprocessor import DataPreprocessor
from data.windowing import WindowGenerator
from models.lstm_autoencoder import LSTMAutoencoder

def generate_synthetic_data(history_hours: int = 168) -> pd.DataFrame:
    """
    Generate synthetic training data for development and testing.
    
    Creates realistic TV-over-IP service metrics with daily usage patterns:
    - Higher traffic during evening hours (peak TV watching time)
    - Lower traffic during night hours
    - Realistic noise and variation
    
    Args:
        history_hours: Number of hours of synthetic data to generate.
                      Default is 168 (7 days) for capturing weekly patterns.
    
    Returns:
        pd.DataFrame: DataFrame with columns:
            - timestamp: DateTime index
            - request_rate: Requests per second
            - latency_p95: 95th percentile latency in ms
            - memory_usage: Memory usage ratio (0-1)
            - error_rate: Errors per second
            - cpu_usage: CPU usage ratio (0-1)
    """
    start_time = datetime.now() - timedelta(hours=history_hours)
    
    # Calculate number of data points based on 30s sampling interval
    # 2 samples per minute * 60 minutes * history_hours
    n_periods = int(history_hours * 60 * 2)
    timestamps = pd.date_range(start=start_time, periods=n_periods, freq='30s')
    
    # Use fixed seed for reproducibility
    np.random.seed(42)
    n_points = len(timestamps)
    
    # Create daily usage pattern using sine wave
    # Peak at hour 20 (8 PM) - evening TV watching time
    # Low at hour 8 (8 AM) - morning hours
    # This matches the mock service pattern for consistency
    hours = np.array([ts.hour for ts in timestamps])
    daily_pattern = 0.5 + 0.4 * np.sin(2 * np.pi * (hours - 8) / 24)
    
    # Generate data matching ACTUAL observed Prometheus patterns (after fixing aggregation bug)
    # Based on real metrics: request_rate ~48, latency_p95 ~0.238s, memory ~0.78GB, error_rate ~0.93, cpu ~0.05
    data = {
        'timestamp': timestamps,
        'request_rate': daily_pattern * 50 + 25 + np.random.normal(0, 3, n_points),  # ~25-75 req/s (matches observed ~48)
        'latency_p95': daily_pattern * 0.12 + 0.18 + np.random.normal(0, 0.03, n_points),  # ~0.18-0.30s (matches observed ~0.238s)
        'memory_usage': daily_pattern * 3e8 + 5e8 + np.random.normal(0, 5e7, n_points),   # ~0.5-0.8GB in bytes (matches observed ~0.78GB)
        'error_rate': daily_pattern * 0.5 + 0.5 + np.random.exponential(0.15, n_points),  # ~0.5-1.5 errors/s (matches observed ~0.93)
        'cpu_usage': daily_pattern * 0.03 + 0.04 + np.random.normal(0, 0.01, n_points)    # ~0.04-0.07 (matches observed ~0.05)
    }
    
    # Asegurar valores positivos
    for col in ['request_rate', 'latency_p95', 'memory_usage', 'error_rate', 'cpu_usage']:
        data[col] = np.maximum(data[col], 0)
    
    return pd.DataFrame(data)

def main():
    """
    Main training pipeline for the LSTM Autoencoder anomaly detector.
    
    Pipeline steps:
        1. Load configuration from YAML files
        2. Collect training data (from Prometheus or synthetic)
        3. Preprocess data (normalization, temporal features)
        4. Create sliding window sequences
        5. Split into train/validation sets
        6. Train LSTM Autoencoder model
        7. Save trained model and preprocessor
        8. Compute and save anomaly detection threshold
    """
    logger = setup_logger()
    logger.info("=== Starting LSTM Autoencoder Training Pipeline ===")
    
    config = Config()
    
    # 1. Recopilar datos
    logger.info("Recopilando datos...")
    
    # Read data collection settings from config
    history_hours = config.get('data.features.collection.history_hours', 168)  # Default 7 days
    
    prometheus_url = config.get('data.prometheus.url')
    prometheus_token = config.get('data.prometheus.token')
    prometheus_timeout = config.get('data.prometheus.timeout_seconds', 30)
    
    # Check if Prometheus URL is actually configured (not empty or placeholder)
    if prometheus_url and prometheus_url.startswith('http') and not '${' in prometheus_url:
        client = PrometheusClient(prometheus_url, token=prometheus_token, timeout=prometheus_timeout)
        df = client.get_tv_metrics(hours_back=history_hours)
        
        # Fallback to synthetic if Prometheus returns no data (e.g., not enough history yet)
        if df.empty:
            logger.warning(f"Prometheus returned no data for {history_hours} hours. Falling back to synthetic data.")
            df = generate_synthetic_data(history_hours)
    else:
        logger.warning("No Prometheus URL configured, generating synthetic data")
        df = generate_synthetic_data(history_hours)
    
    if df.empty:
        logger.error("No data available for training (even synthetic generation failed)")
        return
    
    logger.info(f"Data shape: {df.shape}")
    
    # 2. Preprocesamiento
    logger.info("Preprocessing data...")
    
    # Read preprocessing config
    scaler_type = config.get('data.features.preprocessing.normalization', 'standard')
    temporal_features = config.get('data.features.temporal', {
        'hour_sin': True,
        'hour_cos': True,
        'day_of_week': True,
        'is_weekend': True,
        'is_night': True
    })
    
    preprocessor = DataPreprocessor(scaler_type=scaler_type, temporal_features=temporal_features)
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
    validation_split = config.get('model.training.validation_split', 0.2)
    split_idx = int((1 - validation_split) * len(X))
    X_train, X_val = X[:split_idx], X[split_idx:]
    
    logger.info(f"Training samples: {X_train.shape[0]}, Validation samples: {X_val.shape[0]}")
    
    # 5. Entrenar modelo
    logger.info("Training LSTM Autoencoder...")
    
    input_shape = (X_train.shape[1], X_train.shape[2])
    
    # Read model architecture from config
    encoder_layers = config.get('model.architecture.encoder_layers', [64, 32, 16])
    decoder_layers = config.get('model.architecture.decoder_layers', [16, 32, 64])
    dropout = config.get('model.architecture.dropout', 0.1)
    
    # Read hyperparameters from config
    learning_rate = config.get('model.hyperparameters.learning_rate', 0.001)
    optimizer = config.get('model.hyperparameters.optimizer', 'adam')
    
    model = LSTMAutoencoder(
        input_shape=input_shape,
        encoder_layers=encoder_layers,
        decoder_layers=decoder_layers,
        dropout=dropout,
        learning_rate=learning_rate,
        optimizer=optimizer
    )
    
    # Read training settings from config
    epochs = config.get('model.training.epochs', 50)
    batch_size = config.get('model.training.batch_size', 32)
    early_stopping = config.get('model.training.early_stopping', True)
    patience = config.get('model.training.patience', 10)
    verbose = config.get('model.settings.verbose_training', 1)
    
    history = model.train(
        X_train=X_train,
        X_val=X_val,
        epochs=epochs,
        batch_size=batch_size,
        early_stopping=early_stopping,
        patience=patience,
        verbose=verbose
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
