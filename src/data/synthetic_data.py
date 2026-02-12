"""
Synthetic data generation for LSTM Autoencoder anomaly detection.

Provides unified, realistic TV-over-IP metric generation for training,
inference fallback, and evaluation. Formulas match the mock service and
Prometheus queries (see config/data.yaml for metric definitions).

Usage:
    Training fallback:    generate_synthetic_data(history_hours=168)
    Inference fallback:   generate_synthetic_data(minutes_back=30)
    Evaluation:           generate_test_data_with_anomalies(history_hours=24, seed=123)
"""

import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from typing import Optional, Tuple, List


# Verified against live Prometheus at load=0.114 (01:37 UTC, 2026-02-12).
# Formulas derived from mock_service/app.py simulate_traffic() and PromQL queries:
#   request_rate = 125 * load  (mock: uniform(50,200)*load, avg=125*load)
#   error_rate   = 2.5 * load   (mock: 2% of requests)
#   cpu_usage    = 0.125 * load (mock: uniform(0.05,0.2)*load, avg=0.125*load)
#   memory_usage = noisy constant (mock: base_memory * uniform(0.9,1.1), NO daily cycle)
#   latency_p95  = histogram_quantile approx (bucket interpolation adds upward bias)
DAILY_PATTERN_PEAK_HOUR = 14  # 2 PM
DAILY_PATTERN_OFFSET = 8
SAMPLING_FREQ = '30s'
METRIC_COLUMNS = ['request_rate', 'latency_p95', 'memory_usage', 'error_rate', 'cpu_usage']


def _compute_daily_pattern(timestamps: pd.DatetimeIndex) -> np.ndarray:
    """Compute daily usage pattern: peak at 14:00, trough at 02:00."""
    hours = np.array([ts.hour for ts in timestamps])
    return 0.5 + 0.4 * np.sin(2 * np.pi * (hours - DAILY_PATTERN_OFFSET) / 24)


def generate_synthetic_data(
    history_hours: Optional[int] = None,
    minutes_back: Optional[float] = None,
    seed: Optional[int] = None,
    anomaly_multiplier: float = 1.0,
    end_time: Optional[datetime] = None,
) -> pd.DataFrame:
    """
    Generate synthetic TV-over-IP metrics matching mock service patterns.

    Use for training fallback when Prometheus has no data, or for inference
    fallback when Prometheus is unavailable.

    Args:
        history_hours: Number of hours of data (e.g., 168 for 7 days).
                       Ignored if minutes_back is set.
        minutes_back: Number of minutes of data (e.g., 30 for inference).
                     Takes precedence over history_hours.
        seed: Random seed for reproducibility. If None, uses current time.
        anomaly_multiplier: Scale factor for metrics (1.0 = normal, >1.0 = anomaly).
        end_time: End of time range. Defaults to now.

    Returns:
        DataFrame with columns: timestamp, request_rate, latency_p95,
        memory_usage, error_rate, cpu_usage.
    """
    if minutes_back is not None:
        total_minutes = minutes_back
        start = (end_time or datetime.now()) - timedelta(minutes=total_minutes)
        end = end_time or datetime.now()
    else:
        hours = history_hours or 168
        total_minutes = hours * 60
        end = end_time or datetime.now()
        start = end - timedelta(hours=hours)

    n_periods = int(total_minutes * 2)  # 2 samples per minute (30s interval)
    timestamps = pd.date_range(start=start, end=end, periods=n_periods)

    if seed is not None:
        np.random.seed(seed)
    n_points = len(timestamps)

    daily_pattern = _compute_daily_pattern(timestamps)

    # Memory: noisy constant (no daily pattern), base chosen once per dataset
    base_memory = np.random.uniform(500_000_000, 1_500_000_000)

    data = {
        'timestamp': timestamps,
        'request_rate': (125 * daily_pattern) * anomaly_multiplier + np.random.normal(0, 3, n_points),
        'latency_p95': (0.22 * daily_pattern + 0.215) * anomaly_multiplier + np.random.normal(0, 0.015, n_points),
        'memory_usage': base_memory * anomaly_multiplier + np.random.normal(0, base_memory * 0.03, n_points),
        'error_rate': (2.5 * daily_pattern) * anomaly_multiplier + np.random.normal(0, 0.05, n_points),
        'cpu_usage': (0.125 * daily_pattern) * anomaly_multiplier + np.random.normal(0, 0.005, n_points),
    }

    for col in METRIC_COLUMNS:
        data[col] = np.maximum(data[col], 0)

    return pd.DataFrame(data)


def generate_test_data_with_anomalies(
    history_hours: int = 24,
    seed: int = 123,
) -> Tuple[pd.DataFrame, np.ndarray]:
    """
    Generate test data with known anomalies for model evaluation.

    Uses the same base formulas as generate_synthetic_data, then injects
    three anomaly types: latency spike, request drop, memory leak.

    Args:
        history_hours: Hours of data to generate (default: 24).
        seed: Random seed for reproducibility.

    Returns:
        Tuple of (DataFrame with metrics, binary labels array: 1=anomaly, 0=normal).
    """
    df = generate_synthetic_data(history_hours=history_hours, seed=seed)
    n_points = len(df)
    labels = np.zeros(n_points)
    anomaly_indices: List[int] = []

    # Anomaly 1: Latency spike (10:00–10:30)
    start_1 = 10 * 120
    end_1 = start_1 + 60
    df.loc[df.index[start_1:end_1], 'latency_p95'] *= 3
    anomaly_indices.extend(range(start_1, min(end_1, n_points)))

    # Anomaly 2: Request rate drop (15:00–15:15)
    start_2 = 15 * 120
    end_2 = start_2 + 30
    df.loc[df.index[start_2:end_2], 'request_rate'] *= 0.1
    anomaly_indices.extend(range(start_2, min(end_2, n_points)))

    # Anomaly 3: Memory leak pattern (20:00–21:00) — adds 0–40% of baseline
    start_3 = 20 * 120
    end_3 = min(start_3 + 120, n_points)
    leak_len = end_3 - start_3
    baseline = df['memory_usage'].iloc[start_3]
    leak_pattern = np.linspace(0, 0.4 * baseline, leak_len)
    df.loc[df.index[start_3:end_3], 'memory_usage'] += leak_pattern
    anomaly_indices.extend(range(start_3, end_3))

    for idx in anomaly_indices:
        if idx < n_points:
            labels[idx] = 1

    for col in METRIC_COLUMNS:
        df[col] = np.maximum(df[col], 0)

    return df, labels
