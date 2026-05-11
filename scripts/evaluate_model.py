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
import csv
import os
import sys
from datetime import datetime

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


def _error_stats(errors: np.ndarray) -> dict:
    """Return compact distribution stats for one reconstruction-error group."""
    if len(errors) == 0:
        return {
            'count': 0,
            'mean': np.nan,
            'std': np.nan,
            'min': np.nan,
            'p50': np.nan,
            'p95': np.nan,
            'p99': np.nan,
            'max': np.nan,
        }

    return {
        'count': int(len(errors)),
        'mean': float(np.mean(errors)),
        'std': float(np.std(errors)),
        'min': float(np.min(errors)),
        'p50': float(np.percentile(errors, 50)),
        'p95': float(np.percentile(errors, 95)),
        'p99': float(np.percentile(errors, 99)),
        'max': float(np.max(errors)),
    }


def _format_stats(label: str, stats: dict) -> str:
    """Format distribution stats to mirror the evaluation plot legend/story."""
    return (
        f"{label}: count={stats['count']} "
        f"mean={stats['mean']:.6f} std={stats['std']:.6f} "
        f"p50={stats['p50']:.6f} p95={stats['p95']:.6f} "
        f"p99={stats['p99']:.6f} max={stats['max']:.6f}"
    )


def _timeline_summary(
    window_timestamps: np.ndarray,
    y_true: np.ndarray,
    y_pred: np.ndarray,
    reconstruction_errors: np.ndarray,
) -> dict:
    """Summarize the timeline panel as first/peak detection facts."""
    anomaly_indices = np.where(y_true == 1)[0]
    detection_indices = np.where((y_pred == 1) & (y_true == 1))[0]
    predicted_indices = np.where(y_pred == 1)[0]

    first_anomaly_idx = int(anomaly_indices[0]) if len(anomaly_indices) else None
    first_detection_idx = int(detection_indices[0]) if len(detection_indices) else None
    first_prediction_idx = int(predicted_indices[0]) if len(predicted_indices) else None
    peak_idx = int(np.argmax(reconstruction_errors)) if len(reconstruction_errors) else None

    detection_delay_windows = None
    if first_anomaly_idx is not None and first_detection_idx is not None:
        detection_delay_windows = first_detection_idx - first_anomaly_idx

    def _timestamp(idx):
        if idx is None:
            return None
        return pd.Timestamp(window_timestamps[idx]).isoformat()

    return {
        'first_anomaly_idx': first_anomaly_idx,
        'first_anomaly_ts': _timestamp(first_anomaly_idx),
        'first_detection_idx': first_detection_idx,
        'first_detection_ts': _timestamp(first_detection_idx),
        'first_prediction_idx': first_prediction_idx,
        'first_prediction_ts': _timestamp(first_prediction_idx),
        'detection_delay_windows': detection_delay_windows,
        'peak_error': float(reconstruction_errors[peak_idx]) if peak_idx is not None else np.nan,
        'peak_error_ts': _timestamp(peak_idx),
    }


def _append_iteration_csv(row: dict, path: str = 'evaluation/evaluation_iterations.csv') -> None:
    """Append one compact evaluation row for comparing tuning iterations."""
    file_exists = os.path.exists(path)
    with open(path, 'a', newline='') as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=list(row.keys()))
        if not file_exists:
            writer.writeheader()
        writer.writerow(row)


def _evaluate_at_threshold(
    threshold: float,
    threshold_percentile,
    reconstruction_errors: np.ndarray,
    y_true: np.ndarray,
    window_timestamps: np.ndarray,
    config: Config,
    window_size: int,
    stride: int,
) -> dict:
    """Compute and log the same result story shown in the evaluation plot."""
    y_pred = (reconstruction_errors > threshold).astype(int)

    precision = precision_score(y_true, y_pred, zero_division=0)
    recall = recall_score(y_true, y_pred, zero_division=0)
    f1 = f1_score(y_true, y_pred, zero_division=0)
    accuracy = accuracy_score(y_true, y_pred)

    cm = confusion_matrix(y_true, y_pred, labels=[0, 1])
    tn, fp, fn, tp = cm.ravel()

    normal_errors = reconstruction_errors[y_true == 0]
    anomaly_errors = reconstruction_errors[y_true == 1]
    normal_stats = _error_stats(normal_errors)
    anomaly_stats = _error_stats(anomaly_errors)
    timeline = _timeline_summary(window_timestamps, y_true, y_pred, reconstruction_errors)

    iteration_row = {
        'run_timestamp': datetime.now().isoformat(timespec='seconds'),
        'window_size': window_size,
        'stride': stride,
        'encoder_layers': config.get('model.architecture.encoder_layers', [64, 32, 16]),
        'decoder_layers': config.get('model.architecture.decoder_layers', [16, 32, 64]),
        'dropout': config.get('model.architecture.dropout', 0.1),
        'learning_rate': config.get('model.hyperparameters.learning_rate', 0.001),
        'threshold_percentile': threshold_percentile,
        'threshold': float(threshold),
        'accuracy': float(accuracy),
        'precision': float(precision),
        'recall': float(recall),
        'f1_score': float(f1),
        'tn': int(tn),
        'fp': int(fp),
        'fn': int(fn),
        'tp': int(tp),
        'normal_count': normal_stats['count'],
        'normal_mean': normal_stats['mean'],
        'normal_p95': normal_stats['p95'],
        'normal_p99': normal_stats['p99'],
        'normal_max': normal_stats['max'],
        'anomaly_count': anomaly_stats['count'],
        'anomaly_mean': anomaly_stats['mean'],
        'anomaly_p50': anomaly_stats['p50'],
        'anomaly_p95': anomaly_stats['p95'],
        'anomaly_p99': anomaly_stats['p99'],
        'anomaly_max': anomaly_stats['max'],
        'first_anomaly_ts': timeline['first_anomaly_ts'],
        'first_detection_ts': timeline['first_detection_ts'],
        'detection_delay_windows': timeline['detection_delay_windows'],
        'peak_error': timeline['peak_error'],
        'peak_error_ts': timeline['peak_error_ts'],
    }

    return {
        'threshold': float(threshold),
        'threshold_percentile': threshold_percentile,
        'accuracy': accuracy,
        'precision': precision,
        'recall': recall,
        'f1_score': f1,
        'confusion_matrix': cm,
        'normal_error_stats': normal_stats,
        'anomaly_error_stats': anomaly_stats,
        'timeline': timeline,
        'iteration_row': iteration_row,
        'y_pred': y_pred,
    }


def _log_evaluation_summary(summary: dict, logger, title: str = None) -> None:
    """Print a compact text version of the four evaluation plot panels."""
    if title:
        logger.info(title)

    threshold = summary['threshold']
    normal_stats = summary['normal_error_stats']
    anomaly_stats = summary['anomaly_error_stats']
    timeline = summary['timeline']
    tn, fp, fn, tp = summary['confusion_matrix'].ravel()

    logger.info("=== RECONSTRUCTION ERROR DISTRIBUTION ===")
    logger.info(f"Threshold: {threshold:.6f}")
    logger.info(_format_stats("Normal", normal_stats))
    logger.info(_format_stats("Anomaly", anomaly_stats))

    logger.info("=== DETECTION TIMELINE ===")
    logger.info(f"First anomaly timestamp: {timeline['first_anomaly_ts']}")
    logger.info(f"First detected anomaly timestamp: {timeline['first_detection_ts']}")
    logger.info(f"Detection delay (windows): {timeline['detection_delay_windows']}")
    logger.info(f"Peak reconstruction error: {timeline['peak_error']:.6f}")
    logger.info(f"Peak reconstruction error timestamp: {timeline['peak_error_ts']}")

    logger.info("=== CONFUSION MATRIX ===")
    logger.info(f"TN: {tn}, FP: {fp}")
    logger.info(f"FN: {fn}, TP: {tp}")

    logger.info("=== EVALUATION METRICS ===")
    logger.info(f"Accuracy:  {summary['accuracy']:.3f}")
    logger.info(f"Precision: {summary['precision']:.3f}")
    logger.info(f"Recall:    {summary['recall']:.3f}")
    logger.info(f"F1-Score:  {summary['f1_score']:.3f}")


def _parse_threshold_sweep(value: str) -> list:
    """Parse a comma-separated percentile list from CLI."""
    if not value:
        return []
    return [float(part.strip()) for part in value.split(',') if part.strip()]


def evaluate_model(headless: bool = False, sweep_thresholds: list = None):
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
    
    saved_threshold = float(np.load('models/anomaly_threshold.npy'))
    logger.info(f"Anomaly threshold: {saved_threshold:.4f}")
    
    # 5. Compute reconstruction errors
    reconstruction_errors = model.compute_reconstruction_error(X_test)
    logger.info(f"Reconstruction error - Mean: {reconstruction_errors.mean():.4f}, Std: {reconstruction_errors.std():.4f}")
    logger.info(f"Reconstruction error - Min: {reconstruction_errors.min():.4f}, Max: {reconstruction_errors.max():.4f}")
    
    # 6. Classify anomalies
    window_timestamps = np.array([df_test['timestamp'].iloc[i * stride] for i in range(len(X_test))])
    normal_errors = reconstruction_errors[y_true == 0]

    os.makedirs('evaluation/', exist_ok=True)

    summaries = []
    primary_summary = _evaluate_at_threshold(
        saved_threshold,
        config.get('alerting.threshold.percentile', None),
        reconstruction_errors,
        y_true,
        window_timestamps,
        config,
        window_size,
        stride,
    )
    _log_evaluation_summary(primary_summary, logger, "=== SAVED THRESHOLD EVALUATION ===")
    _append_iteration_csv(primary_summary['iteration_row'])
    summaries.append(primary_summary)

    for percentile in sweep_thresholds or []:
        sweep_threshold = float(np.percentile(normal_errors, percentile))
        summary = _evaluate_at_threshold(
            sweep_threshold,
            percentile,
            reconstruction_errors,
            y_true,
            window_timestamps,
            config,
            window_size,
            stride,
        )
        _log_evaluation_summary(
            summary,
            logger,
            f"=== THRESHOLD SWEEP: normal_error_p{percentile:g} ===",
        )
        _append_iteration_csv(summary['iteration_row'])
        summaries.append(summary)

    logger.info("Iteration summary appended to evaluation/evaluation_iterations.csv")
    
    # 9. Generate visualizations
    # Plot 1: Distribución de errores
    plt.figure(figsize=(12, 8))
    
    plt.subplot(2, 2, 1)
    plt.hist(reconstruction_errors[y_true == 0], bins=50, alpha=0.7, label='Normal', density=True)
    plt.hist(reconstruction_errors[y_true == 1], bins=50, alpha=0.7, label='Anomalía', density=True)
    plt.axvline(saved_threshold, color='red', linestyle='--', label=f'Threshold: {saved_threshold:.4f}')
    plt.xlabel('Reconstruction Error')
    plt.ylabel('Density')
    plt.legend()
    plt.title('Reconstruction Error Distribution')
    
    # Plot 2: Timeline de anomalías
    plt.subplot(2, 2, 2)
    plt.scatter(window_timestamps[y_true == 0], reconstruction_errors[y_true == 0], 
                c='blue', alpha=0.6, label='Normal', s=20)
    plt.scatter(window_timestamps[y_true == 1], reconstruction_errors[y_true == 1], 
                c='red', alpha=0.8, label='Ground Truth Anomaly', s=30)
    plt.axhline(saved_threshold, color='red', linestyle='--', alpha=0.7)
    plt.xticks(rotation=45)
    plt.ylabel('Reconstruction Error')
    plt.legend()
    plt.title('Detection Timeline')
    
    # Plot 3: Matriz de confusión
    plt.subplot(2, 2, 3)
    sns.heatmap(primary_summary['confusion_matrix'], annot=True, fmt='d', cmap='Blues')
    plt.ylabel('Actual')
    plt.xlabel('Predicted')
    plt.title('Matriz de Confusión')
    
    # Plot 4: Métricas
    plt.subplot(2, 2, 4)
    metrics = ['Accuracy', 'Precision', 'Recall', 'F1-Score']
    values = [
        primary_summary['accuracy'],
        primary_summary['precision'],
        primary_summary['recall'],
        primary_summary['f1_score'],
    ]
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
        'accuracy': primary_summary['accuracy'],
        'precision': primary_summary['precision'],
        'recall': primary_summary['recall'],
        'f1_score': primary_summary['f1_score'],
        'threshold': saved_threshold,
        'reconstruction_errors': reconstruction_errors,
        'confusion_matrix': primary_summary['confusion_matrix'],
        'normal_error_stats': primary_summary['normal_error_stats'],
        'anomaly_error_stats': primary_summary['anomaly_error_stats'],
        'timeline': primary_summary['timeline'],
        'sweep_results': summaries,
    }

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Evaluate LSTM Autoencoder on test data')
    parser.add_argument('--headless', action='store_true',
                        help='Skip interactive plot display (for CI/automation)')
    parser.add_argument('--sweep-thresholds', default='',
                        help='Comma-separated normal-error percentiles to evaluate, e.g. 95,97.5,99,99.5')
    args = parser.parse_args()
    results = evaluate_model(
        headless=args.headless,
        sweep_thresholds=_parse_threshold_sweep(args.sweep_thresholds),
    )
