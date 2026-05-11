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
    - Model weights and config: path from config model.paths.base (default models/lstm_autoencoder.h5)
      → creates .weights.h5 and _config.json
    - models/preprocessor.joblib: Fitted preprocessor (scaler type from config, typically fixed_minmax)
    - models/anomaly_threshold.npy: Computed anomaly threshold

Usage:
    python scripts/train.py

Author: Ing. Christopher Charaf
"""

import os
import sys
import numpy as np
import pandas as pd
# Add src directory to Python path for imports
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'src'))

from utils.config import Config
from utils.logging import setup_logger
from data.prometheus_client import PrometheusClient
from data.preprocessor import DataPreprocessor
from data.windowing import WindowGenerator
from data.synthetic_data import generate_synthetic_data
from models.lstm_autoencoder import LSTMAutoencoder

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
    
    # 1. Collect data
    logger.info("Collecting data...")
    
    # Read data collection settings from config
    history_hours = config.get('data.features.collection.history_hours', 168)  # Default 7 days
    sampling_interval = config.get('data.features.collection.sampling_interval', '30s')
    
    prometheus_url = config.get('data.prometheus.url')
    prometheus_token = config.get('data.prometheus.token')
    prometheus_timeout = config.get('data.prometheus.timeout_seconds', 30)
    
    # Load metric queries from config (list of dicts with query/name/aggregation)
    metric_queries = config.get('data.metrics.queries', None)
    
    # Check if Prometheus URL is actually configured (not empty or placeholder)
    if prometheus_url and prometheus_url.startswith('http') and not '${' in prometheus_url:
        try:
            client = PrometheusClient(prometheus_url, token=prometheus_token, timeout=prometheus_timeout)
            df = client.get_tv_metrics(hours_back=history_hours, queries=metric_queries, step=sampling_interval)
        except Exception as e:
            logger.warning("Prometheus unavailable (%s). Using synthetic data.", e)
            df = pd.DataFrame()

        # Fallback to synthetic if Prometheus returns no data (e.g., not enough history yet)
        if df.empty:
            logger.warning(
                f"Prometheus returned no data for {history_hours} hours. Falling back to synthetic data."
            )
            if history_hours >= 720:
                logger.info(
                    "Synthetic generation for long history can take many minutes "
                    "(e.g. ~90 days: often 10-20+ min) before training starts."
                )
            df = generate_synthetic_data(history_hours=history_hours, seed=42)
    else:
        logger.warning("No Prometheus URL configured, generating synthetic data")
        if history_hours >= 720:
            logger.info(
                "Synthetic generation for long history can take many minutes "
                "(e.g. ~90 days: often 10-20+ min) before training starts."
            )
        df = generate_synthetic_data(history_hours=history_hours, seed=42)
    
    if df.empty:
        logger.error("No data available for training (even synthetic generation failed)")
        return
    
    # Validate minimum data: need at least 5 windows to form meaningful train/val split
    window_size = config.get('windowing.window_size', 20)
    min_rows = window_size * 5
    if len(df) < min_rows:
        logger.warning(f"Prometheus returned only {len(df)} rows, need >= {min_rows} "
                       f"(window_size={window_size} x 5). Falling back to synthetic data.")
        if history_hours >= 720:
            logger.info(
                "Synthetic generation for long history can take many minutes "
                "(e.g. ~90 days: often 10-20+ min) before training starts."
            )
        df = generate_synthetic_data(history_hours=history_hours, seed=42)
    
    logger.info(f"Data shape: {df.shape}")
    
    # 2. Preprocess
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
    fixed_bounds = config.get('data.features.preprocessing.fixed_bounds', {})
    
    preprocessor = DataPreprocessor(
        scaler_type=scaler_type,
        temporal_features=temporal_features,
        fixed_bounds=fixed_bounds
    )
    df_processed = preprocessor.fit_transform(df)
    
    os.makedirs('models/', exist_ok=True)
    preprocessor.save_scaler('models/preprocessor.joblib')
    
    # 3. Create sliding windows
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
    
    # 5. Train model
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

    model_base = config.get('model.paths.base', 'models/lstm_autoencoder.h5')

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
    
    # 6. Save model
    model.save(model_base)
    logger.info(f"Model saved to {model_base}")
    
    # 7. Compute threshold
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
    
    # 8. Final statistics
    final_loss = history['loss'][-1]
    final_val_loss = history['val_loss'][-1] if 'val_loss' in history else None
    
    logger.info(f"Final training loss: {final_loss:.4f}")
    if final_val_loss:
        logger.info(f"Final validation loss: {final_val_loss:.4f}")
    
    logger.info("=== Training completed ===")

if __name__ == "__main__":
    main()
