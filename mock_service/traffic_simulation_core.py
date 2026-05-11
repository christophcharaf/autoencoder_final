"""
Shared TV-over-IP traffic simulation — single source of truth for:
  - mock_service/app.py (live Prometheus metrics)
  - src/data/synthetic_data.py (offline training / fallback series)

Logic mirrors simulate_traffic() in app.py: same load curve, per-request endpoint/latency/error
draws, memory/cpu rules, and optional anomalies.

For long offline runs, use simulate_one_second_compact() to avoid allocating RequestEvent
lists every simulated second.
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass
from datetime import datetime
from typing import Callable, List

import numpy as np

# Histogram buckets must match REQUEST_DURATION in app.py
DURATION_BUCKETS: List[float] = [0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0]

ENDPOINTS = ["/stream", "/api/channels", "/api/epg", "/health"]

ERROR_TYPES = ["500", "502", "503", "504"]

AnomalyPredicate = Callable[[str, datetime], bool]

_NB = len(DURATION_BUCKETS) + 1
_NE = len(ENDPOINTS)


def get_daily_load_factor(hour: int, rng: random.Random) -> float:
    """
    Same as mock get_daily_load_factor(): sine diurnal curve + noise, clamped to [0.1, 1.0].
    """
    base_factor = 0.5 + 0.4 * math.sin(2 * math.pi * (hour - 8) / 24)
    noise = rng.uniform(-0.05, 0.05)
    return max(0.1, min(1.0, base_factor + noise))


@dataclass
class RequestEvent:
    endpoint: str
    latency: float
    is_error: bool
    error_type: str


@dataclass
class SecondSample:
    """One simulated second: per-request events plus resource/cpu (matches mock loop)."""

    events: List[RequestEvent]
    memory_bytes: float
    cpu_seconds: float

    @property
    def requests(self) -> int:
        return len(self.events)

    @property
    def errors(self) -> int:
        return sum(1 for e in self.events if e.is_error)

    def histogram_bucket_increments(self) -> np.ndarray:
        """Pooled histogram (all endpoints); matches sum of per-endpoint counters in Prometheus."""
        if not self.events:
            return np.zeros(_NB, dtype=np.float64)
        latencies = np.array([e.latency for e in self.events], dtype=np.float64)
        return _histogram_inc_from_latencies(latencies)

    def per_endpoint_histogram_bucket_increments(self) -> np.ndarray:
        """
        Shape (len(ENDPOINTS), len(DURATION_BUCKETS)+1): cumulative-bucket counter deltas
        per {endpoint} label, matching separate Histogram series in the mock.
        """
        out = np.zeros((_NE, _NB), dtype=np.float64)
        for e in self.events:
            ei = ENDPOINTS.index(e.endpoint)
            out[ei] += _histogram_inc_from_latencies(np.array([e.latency], dtype=np.float64))
        return out


@dataclass
class SecondCompact:
    """One simulated second without RequestEvent materialization (fast path for offline series)."""

    memory_bytes: float
    cpu_seconds: float
    requests: int
    errors: int
    hist_ep_delta: np.ndarray  # shape (_NE, _NB)


def _histogram_inc_from_latencies(latencies: np.ndarray) -> np.ndarray:
    """
    Prometheus cumulative histogram: one observe() increments all bucket counters
    with le >= value (implemented via searchsorted 'right' index then cumsum of counts).
    """
    edges = np.asarray(DURATION_BUCKETS, dtype=np.float64)
    n_buckets = len(DURATION_BUCKETS) + 1
    if latencies.size == 0:
        return np.zeros(n_buckets, dtype=np.float64)

    idx = np.searchsorted(edges, latencies, side="right")
    counts = np.bincount(idx, minlength=n_buckets)
    return np.cumsum(counts).astype(np.float64)


def _simulate_one_second_core(
    dt: datetime,
    rng: random.Random,
    base_memory: float,
    is_anomaly: AnomalyPredicate,
) -> tuple[
    float,
    float,
    int,
    int,
    np.ndarray,
    List[int],
    List[float],
    List[bool],
    List[str],
]:
    """
    Shared draws / histogram. Returns:
      memory, cpu, num_requests, n_errors, hist_ep (ne, nb),
      ep_idx, latencies, is_errs, err_labels (empty lists if n_req == 0).
    """
    load_factor = get_daily_load_factor(dt.hour, rng)
    num_requests = int(rng.uniform(50, 200) * load_factor)

    if is_anomaly("traffic_drop", dt):
        num_requests = int(num_requests * 0.1)

    if is_anomaly("memory_spike", dt):
        memory = rng.uniform(3_000_000_000, 4_000_000_000)
    else:
        memory = base_memory * rng.uniform(0.9, 1.1)

    cpu_increment = rng.uniform(0.05, 0.2) * load_factor
    if is_anomaly("latency_spike", dt) or is_anomaly("memory_spike", dt):
        cpu_increment *= 2.0

    if num_requests <= 0:
        return (
            float(memory),
            float(cpu_increment),
            0,
            0,
            np.zeros((_NE, _NB), dtype=np.float64),
            [],
            [],
            [],
            [],
        )

    error_rate = 0.3 if is_anomaly("error_burst", dt) else 0.02
    ep_idx = rng.choices(range(_NE), k=num_requests)
    r_lat = [rng.random() for _ in range(num_requests)]
    if is_anomaly("latency_spike", dt):
        latencies = [2.0 + 8.0 * r for r in r_lat]
    else:
        scale = 1.0 + load_factor * 0.5
        lo, hi = 0.01 * scale, 0.2 * scale
        latencies = [lo + (hi - lo) * r for r in r_lat]

    r_err = [rng.random() for _ in range(num_requests)]
    is_errs = [r < error_rate for r in r_err]
    err_labels = [rng.choice(ERROR_TYPES) if ie else "" for ie in is_errs]

    ep_arr = np.asarray(ep_idx, dtype=np.intp)
    lat_arr = np.asarray(latencies, dtype=np.float64)
    hist_ep = np.zeros((_NE, _NB), dtype=np.float64)
    for ei in range(_NE):
        m = ep_arr == ei
        if np.any(m):
            hist_ep[ei] = _histogram_inc_from_latencies(lat_arr[m])

    n_err = int(sum(is_errs))

    return (
        float(memory),
        float(cpu_increment),
        num_requests,
        n_err,
        hist_ep,
        ep_idx,
        latencies,
        is_errs,
        err_labels,
    )


def simulate_one_second_compact(
    dt: datetime,
    rng: random.Random,
    base_memory: float,
    is_anomaly: AnomalyPredicate,
) -> SecondCompact:
    """Same RNG semantics as simulate_one_second, without RequestEvent allocation."""
    mem, cpu, n_req, n_err, hist_ep, _, _, _, _ = _simulate_one_second_core(
        dt, rng, base_memory, is_anomaly
    )
    return SecondCompact(
        memory_bytes=mem,
        cpu_seconds=cpu,
        requests=n_req,
        errors=n_err,
        hist_ep_delta=hist_ep,
    )


def simulate_one_second(
    dt: datetime,
    rng: random.Random,
    base_memory: float,
    is_anomaly: AnomalyPredicate,
) -> SecondSample:
    """
    One second of traffic — same control flow as mock simulate_traffic() inner loop.

    Args:
        dt: Wall time (used for hour-of-day load).
        rng: Injected PRNG for reproducibility offline.
        base_memory: Resident memory baseline for this run (set once per simulation).
        is_anomaly: Predicate (name, dt) -> bool; e.g. lambda n, _: state.is_active(n).
    """
    mem, cpu, n_req, _n_err, _, ep_idx, latencies, is_errs, err_labels = _simulate_one_second_core(
        dt, rng, base_memory, is_anomaly
    )
    events = [
        RequestEvent(ENDPOINTS[ep_idx[i]], latencies[i], is_errs[i], err_labels[i])
        for i in range(n_req)
    ]
    return SecondSample(
        events=events,
        memory_bytes=mem,
        cpu_seconds=cpu,
    )


def new_base_memory(rng: random.Random) -> float:
    """Same range as mock: 500MB–1.5GB."""
    return rng.uniform(500_000_000, 1_500_000_000)
