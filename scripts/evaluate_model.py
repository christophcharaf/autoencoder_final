#!/usr/bin/env python3
"""
Model evaluation script for LSTM Autoencoder anomaly detection.

Generates test data with known anomalies, runs inference, and computes
precision, recall, F1, and confusion matrix. Saves evaluation plots
to evaluation/model_evaluation.png.

Model path is configurable via config model.paths.base (default models/lstm_autoencoder.h5).

Usage:
    python scripts/evaluate_model.py           # Interactive (shows plot window)
    python scripts/evaluate_model.py --headless  # Non-blocking (CI/automation)
"""

import argparse
import os
import sys
import numpy as np

# Set non-interactive backend before importing pyplot (for headless/CI)
# Check argv without parsing to avoid consuming args when module is imported
if '--headless' in sys.argv:
    import matplotlib
    matplotlib.use('Agg')

import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from sklearn.metrics import (
    confusion_matrix,
    precision_score,
    recall_score,
    f1_score,
    accuracy_score,
)

sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'src'))

from utils.config import Config
from utils.logging import setup_logger
from data.preprocessor import DataPreprocessor
from data.windowing import WindowGenerator
from data.synthetic_data import generate_test_data_with_anomalies
from models.lstm_autoencoder import LSTMAutoencoder


def evaluate_model(headless: bool = False):
    """
    Evaluate the trained model on test data with known anomalies.

    Args:
        headless: If True, skip plt.show() (non-blocking; for CI/automation).
    """
    logger = setup_logger()
    logger.info("=== Evaluating trained model ===")
    
    config = Config()
    model_base = config.get('model.paths.base', 'models/lstm_autoencoder.h5')

    # 1. Generate test data with known anomalies
    df_test, true_labels = generate_test_data_with_anomalies(history_hours=24, seed=123)
    logger.info(f"Test data generated: {df_test.shape}")
    logger.info(f"Ground truth anomalies: {np.sum(true_labels)} of {len(true_labels)} ({100*np.sum(true_labels)/len(true_labels):.1f}%)")
    
    # 2. Load preprocessor
    preprocessor = DataPreprocessor()
    preprocessor.load_scaler('models/preprocessor.joblib')
    df_processed = preprocessor.transform(df_test)
    
    # 3. Create sliding windows
    window_size = config.get('windowing.window_size', 20)
    stride = config.get('windowing.stride', 20)
    
    windower = WindowGenerator(window_size=window_size, stride=stride)
    X_test, _ = windower.create_sequences(df_processed)
    
    # Align labels with windows (window is anomalous if any point inside is anomalous)
    n_windows = len(X_test)
    window_labels = []
    for i in range(n_windows):
        start_idx = i * stride
        end_idx = start_idx + window_size
        # Window is anomalous if it contains at least one anomalous point
        window_has_anomaly = np.any(true_labels[start_idx:end_idx])
        window_labels.append(int(window_has_anomaly))
    
    y_true = np.array(window_labels)
    logger.info(f"Test windows: {len(X_test)}")
    logger.info(f"Anomalous windows: {np.sum(y_true)} of {len(y_true)} ({100*np.sum(y_true)/len(y_true):.1f}%)")
    
    # 4. Load model and threshold
    input_shape = (X_test.shape[1], X_test.shape[2])
    model = LSTMAutoencoder(input_shape=input_shape)
    model.load(model_base)
    
    threshold = np.load('models/anomaly_threshold.npy')
    logger.info(f"Anomaly threshold: {threshold:.4f}")
    
    # 5. Compute reconstruction errors
    reconstruction_errors = model.compute_reconstruction_error(X_test)
    logger.info(f"Reconstruction error - Mean: {reconstruction_errors.mean():.4f}, Std: {reconstruction_errors.std():.4f}")
    logger.info(f"Reconstruction error - Min: {reconstruction_errors.min():.4f}, Max: {reconstruction_errors.max():.4f}")
    
    # 6. Classify anomalies
    y_pred = (reconstruction_errors > threshold).astype(int)
    
    # 7. Compute metrics
    precision = precision_score(y_true, y_pred, zero_division=0)
    recall = recall_score(y_true, y_pred, zero_division=0)
    f1 = f1_score(y_true, y_pred, zero_division=0)
    accuracy = accuracy_score(y_true, y_pred)
    
    logger.info("=== EVALUATION RESULTS ===")
    logger.info(f"Accuracy:  {accuracy:.3f}")
    logger.info(f"Precision: {precision:.3f}")  
    logger.info(f"Recall:    {recall:.3f}")
    logger.info(f"F1-Score:  {f1:.3f}")
    
    # 8. Confusion matrix
    cm = confusion_matrix(y_true, y_pred)
    logger.info("Confusion matrix:")
    logger.info(f"TN: {cm[0,0]}, FP: {cm[0,1]}")
    logger.info(f"FN: {cm[1,0]}, TP: {cm[1,1]}")
    
    # 9. Generate visualizations
    os.makedirs('evaluation/', exist_ok=True)
    
    # Plot 1: Distribución de errores
    plt.figure(figsize=(12, 8))
    
    plt.subplot(2, 2, 1)
    plt.hist(reconstruction_errors[y_true == 0], bins=50, alpha=0.7, label='Normal', density=True)
    plt.hist(reconstruction_errors[y_true == 1], bins=50, alpha=0.7, label='Anomalía', density=True)
    plt.axvline(threshold, color='red', linestyle='--', label=f'Threshold: {threshold:.4f}')
    plt.xlabel('Reconstruction Error')
    plt.ylabel('Density')
    plt.legend()
    plt.title('Reconstruction Error Distribution')
    
    # Plot 2: Timeline de anomalías
    plt.subplot(2, 2, 2)
    window_timestamps = np.array([df_test['timestamp'].iloc[i * stride] for i in range(len(X_test))])
    plt.scatter(window_timestamps[y_true == 0], reconstruction_errors[y_true == 0], 
                c='blue', alpha=0.6, label='Normal', s=20)
    plt.scatter(window_timestamps[y_true == 1], reconstruction_errors[y_true == 1], 
                c='red', alpha=0.8, label='Ground Truth Anomaly', s=30)
    plt.axhline(threshold, color='red', linestyle='--', alpha=0.7)
    plt.xticks(rotation=45)
    plt.ylabel('Reconstruction Error')
    plt.legend()
    plt.title('Detection Timeline')
    
    # Plot 3: Matriz de confusión
    plt.subplot(2, 2, 3)
    sns.heatmap(cm, annot=True, fmt='d', cmap='Blues')
    plt.ylabel('Actual')
    plt.xlabel('Predicted')
    plt.title('Matriz de Confusión')
    
    # Plot 4: Métricas
    plt.subplot(2, 2, 4)
    metrics = ['Accuracy', 'Precision', 'Recall', 'F1-Score']
    values = [accuracy, precision, recall, f1]
    bars = plt.bar(metrics, values, color=['green', 'blue', 'orange', 'red'])
    plt.ylim(0, 1.1)
    for bar, value in zip(bars, values):
        plt.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.01, 
                f'{value:.3f}', ha='center', va='bottom')
    plt.title('Evaluation Metrics')
    plt.xticks(rotation=45)
    
    plt.tight_layout()
    plt.savefig('evaluation/model_evaluation.png', dpi=300, bbox_inches='tight')
    if not headless:
        plt.show()

    logger.info("Visualizations saved to evaluation/model_evaluation.png")
    logger.info("=== Evaluation completed ===")
    
    return {
        'accuracy': accuracy,
        'precision': precision, 
        'recall': recall,
        'f1_score': f1,
        'threshold': threshold,
        'reconstruction_errors': reconstruction_errors
    }

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Evaluate LSTM Autoencoder on test data')
    parser.add_argument('--headless', action='store_true',
                        help='Skip interactive plot display (for CI/automation)')
    args = parser.parse_args()
    results = evaluate_model(headless=args.headless)
