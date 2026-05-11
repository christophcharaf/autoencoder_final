"""
Synthetic data generation for LSTM Autoencoder anomaly detection.

Builds training/inference series by running the same second-level simulation as the
mock TV-over-IP service (traffic_simulation_core), then applying the same
aggregation semantics as config/data.yaml PromQL:

  rate(...[5m])           -> sliding 300s window over counters
  histogram_quantile    -> classic cumulative histogram (Prometheus-style)
  latency_p95            -> max over {endpoint} series (matches data.yaml aggregation: max)

Use when Prometheus is unavailable or for reproducible evaluation.

Simulation time grows about linearly with span (e.g. ~4s per 24h on a typical laptop);
memory stays O(1) via a 5m sliding window (safe for multi-month histories).
"""

from __future__ import annotations

import math
import random
import sys
from collections import defaultdict, deque
from datetime import datetime, timedelta
from pathlib import Path
from typing import DefaultDict, List, Optional, Tuple

import numpy as np
import pandas as pd

# Resolve mock_service/traffic_simulation_core without packaging the repo
_MOCK_DIR = Path(__file__).resolve().parents[2] / "mock_service"
if str(_MOCK_DIR) not in sys.path:
    sys.path.insert(0, str(_MOCK_DIR))

import traffic_simulation_core as _tsc  # noqa: E402

METRIC_COLUMNS = ["request_rate", "latency_p95", "memory_usage", "error_rate", "cpu_usage"]

# Aligns with PromQL rate(...[5m]) — sliding window length in seconds.
_RATE_WINDOW_SEC = 300


def _prometheus_histogram_quantile(q: float, cum_bucket_rates: np.ndarray) -> float:
    """
    histogram_quantile(q, rate(http_request_duration_seconds_bucket[5m])).
    cum_bucket_rates: rate of each cumulative bucket (+Inf last), aligned with DURATION_BUCKETS.
    """
    upper_bounds = np.array(_tsc.DURATION_BUCKETS + [float("inf")], dtype=np.float64)
    c = np.asarray(cum_bucket_rates, dtype=np.float64).ravel()
    n = len(c)
    if n < 2 or not np.isinf(upper_bounds[-1]):
        return 0.0
    obs = c[-1]
    if obs <= 0:
        return 0.0
    rank = q * obs
    b = int(np.searchsorted(c, rank, side="left"))
    if b >= n:
        b = n - 1
    if b == n - 1:
        return float(upper_bounds[-2])
    if b == 0:
        if c[0] <= 0:
            return float(upper_bounds[0])
        return float(upper_bounds[0] * rank / c[0])
    lower_count = c[b - 1]
    upper_count = c[b]
    width = upper_count - lower_count
    if width <= 0:
        return float(upper_bounds[b])
    fraction = (rank - lower_count) / width
    return float(upper_bounds[b - 1] + fraction * (upper_bounds[b] - upper_bounds[b - 1]))


def _simulate_metrics_dataframe(
    start: datetime,
    end: datetime,
    timestamps: pd.DatetimeIndex,
    rng,
    is_anomaly: _tsc.AnomalyPredicate,
    memory_baseline_period_seconds: Optional[int] = None,
) -> pd.DataFrame:
    """
    Second-resolution mock-faithful simulation; downsample to timestamps.

    Uses a sliding _RATE_WINDOW_SEC buffer so memory stays bounded (multi-month safe).
    For long training spans, memory_baseline_period_seconds can simulate normal
    service restarts with different resident-memory baselines.
    """
    span = max((end - start).total_seconds(), 0.0)
    n_steps = max(int(math.ceil(span)), 0)
    nb = len(_tsc.DURATION_BUCKETS) + 1
    n_endpoints = len(_tsc.ENDPOINTS)

    pending: DefaultDict[int, List[pd.Timestamp]] = defaultdict(list)
    for ts in timestamps:
        sec = (pd.Timestamp(ts) - pd.Timestamp(start)).total_seconds()
        if n_steps <= 0:
            idx_e = 0
        else:
            idx_e = int(max(1, min(math.ceil(sec), n_steps)))
        pending[idx_e].append(ts)

    base_memory = _tsc.new_base_memory(rng)
    ring_req: deque = deque()
    ring_err: deque = deque()
    ring_cpu: deque = deque()
    ring_hist: deque = deque()
    sum_req = 0.0
    sum_err = 0.0
    sum_cpu = 0.0
    sum_hist = np.zeros((n_endpoints, nb), dtype=np.float64)

    rows: List[dict] = []

    def _push_second(d_req: int, d_err: int, d_cpu: float, d_hist: np.ndarray) -> None:
        nonlocal sum_req, sum_err, sum_cpu, sum_hist
        if len(ring_req) >= _RATE_WINDOW_SEC:
            sum_req -= ring_req.popleft()
            sum_err -= ring_err.popleft()
            sum_cpu -= ring_cpu.popleft()
            sum_hist -= ring_hist.popleft()
        ring_req.append(d_req)
        ring_err.append(d_err)
        ring_cpu.append(d_cpu)
        ring_hist.append(d_hist)
        sum_req += d_req
        sum_err += d_err
        sum_cpu += d_cpu
        sum_hist += d_hist

    def _emit_for_idx(ts: pd.Timestamp) -> None:
        wlen = len(ring_req)
        if wlen <= 0:
            dr = de = dc = p95 = 0.0
        else:
            dr = sum_req / wlen
            de = sum_err / wlen
            dc = sum_cpu / wlen
            p95_per_ep = np.zeros(n_endpoints, dtype=np.float64)
            for ei in range(n_endpoints):
                dh = sum_hist[ei] / wlen
                p95_per_ep[ei] = _prometheus_histogram_quantile(0.95, dh)
            p95 = float(np.max(p95_per_ep))
        mem = float(last_memory)
        rows.append(
            {
                "timestamp": ts,
                "request_rate": dr,
                "latency_p95": p95,
                "memory_usage": mem,
                "error_rate": de,
                "cpu_usage": dc,
            }
        )

    last_memory = float(base_memory)
    for s in range(n_steps):
        if (
            memory_baseline_period_seconds
            and s > 0
            and s % memory_baseline_period_seconds == 0
        ):
            base_memory = _tsc.new_base_memory(rng)

        dt = start + timedelta(seconds=s)
        sample = _tsc.simulate_one_second_compact(dt, rng, base_memory, is_anomaly)
        last_memory = sample.memory_bytes
        _push_second(sample.requests, sample.errors, sample.cpu_seconds, sample.hist_ep_delta)
        idx_end = s + 1
        for ts in pending.get(idx_end, ()):
            _emit_for_idx(ts)

    return pd.DataFrame(rows)


def generate_synthetic_data(
    history_hours: Optional[int] = None,
    minutes_back: Optional[float] = None,
    seed: Optional[int] = None,
    anomaly_multiplier: float = 1.0,
    end_time: Optional[datetime] = None,
) -> pd.DataFrame:
    """
    Generate metrics by replaying mock-identical traffic logic at 1s resolution,
    then the same PromQL-style windows as production.

    anomaly_multiplier: optional legacy scaling for inference demos (applied after simulation).
    """
    if minutes_back is not None:
        total_minutes = minutes_back
        end = end_time or datetime.now()
        start = end - timedelta(minutes=total_minutes)
        memory_baseline_period_seconds = None
    else:
        hours = history_hours or 168
        total_minutes = hours * 60
        end = end_time or datetime.now()
        start = end - timedelta(hours=hours)
        memory_baseline_period_seconds = 24 * 60 * 60

    n_periods = int(total_minutes * 2)
    timestamps = pd.date_range(start=start, end=end, periods=n_periods)

    if seed is not None:
        rng = random.Random(seed)
    else:
        rng = random.Random()

    def _no_anomaly(_name: str, _dt: datetime) -> bool:
        return False

    df = _simulate_metrics_dataframe(
        start,
        end,
        timestamps,
        rng,
        _no_anomaly,
        memory_baseline_period_seconds=memory_baseline_period_seconds,
    )

    if anomaly_multiplier != 1.0:
        for col in METRIC_COLUMNS:
            df[col] = np.maximum(df[col] * anomaly_multiplier, 0)

    return df


def generate_test_data_with_anomalies(
    history_hours: int = 24,
    seed: int = 123,
) -> Tuple[pd.DataFrame, np.ndarray]:
    """
    Same simulation core with scheduled anomaly windows (wall-clock from fixed epoch).
    Labels: 1 where any injected window overlaps the sample time (per-row).
    """
    start = datetime(2020, 1, 1, 0, 0, 0)
    end = start + timedelta(hours=history_hours)
    total_minutes = history_hours * 60
    n_periods = int(total_minutes * 2)
    timestamps = pd.date_range(start=start, end=end, periods=n_periods)
    rng = random.Random(seed)

    def is_scheduled(name: str, dt: datetime) -> bool:
        sec = (dt - start).total_seconds()
        if name == "latency_spike" and 10 * 3600 <= sec < 10 * 3600 + 1800:
            return True
        if name == "traffic_drop" and 15 * 3600 <= sec < 15 * 3600 + 900:
            return True
        if name == "memory_spike" and 20 * 3600 <= sec < 21 * 3600:
            return True
        return False

    df = _simulate_metrics_dataframe(start, end, timestamps, rng, is_scheduled)

    labels = np.zeros(len(df), dtype=np.float64)
    for i, ts in enumerate(df["timestamp"]):
        sec = (pd.Timestamp(ts) - pd.Timestamp(start)).total_seconds()
        if (10 * 3600 <= sec < 10 * 3600 + 1800) or (
            15 * 3600 <= sec < 15 * 3600 + 900
        ) or (20 * 3600 <= sec < 21 * 3600):
            labels[i] = 1.0

    return df, labels
