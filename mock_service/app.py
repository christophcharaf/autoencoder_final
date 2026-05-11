#!/usr/bin/env python3
"""
Mock TV-over-IP Service
Exposes Prometheus metrics with realistic traffic patterns and API-triggered anomaly injection.
"""

import time
import random
import threading
from datetime import datetime

from traffic_simulation_core import (
    new_base_memory,
    simulate_one_second,
)
from flask import Flask, request, jsonify
from prometheus_client import (
    Counter, Histogram, Gauge, 
    generate_latest, CONTENT_TYPE_LATEST,
    REGISTRY,
    PROCESS_COLLECTOR, PLATFORM_COLLECTOR, GC_COLLECTOR
)

# Disable default collectors that conflict with our custom metrics
REGISTRY.unregister(PROCESS_COLLECTOR)
REGISTRY.unregister(PLATFORM_COLLECTOR)
REGISTRY.unregister(GC_COLLECTOR)

app = Flask(__name__)

# ============================================================================
# Prometheus Metrics (matching config/data.yaml queries)
# ============================================================================

# Counter: http_requests_total - tracks total HTTP requests
REQUEST_COUNT = Counter(
    'http_requests_total', 
    'Total HTTP requests',
    ['method', 'endpoint', 'status']
)

# Histogram: http_request_duration_seconds - tracks request latency
REQUEST_DURATION = Histogram(
    'http_request_duration_seconds',
    'Request latency in seconds',
    ['endpoint'],
    buckets=[0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0]
)

# Counter: http_request_errors_total - tracks HTTP errors
ERROR_COUNT = Counter(
    'http_request_errors_total',
    'Total HTTP errors',
    ['method', 'endpoint', 'error_type']
)

# Gauge: process_resident_memory_bytes - memory usage
MEMORY_USAGE = Gauge(
    'process_resident_memory_bytes',
    'Resident memory size in bytes'
)

# Counter: process_cpu_seconds_total - CPU time
CPU_SECONDS = Counter(
    'process_cpu_seconds_total',
    'Total CPU time spent in seconds'
)

# Gauge: up - service availability
SERVICE_UP = Gauge(
    'up',
    'Service availability (1 = up, 0 = down)'
)

# ============================================================================
# Anomaly State Management
# ============================================================================

class AnomalyState:
    """Manages active anomalies and their durations."""
    
    def __init__(self):
        self.active_anomalies = {}
        self.lock = threading.Lock()
    
    def add_anomaly(self, anomaly_type: str, duration: int):
        """Add an anomaly that will be active for the specified duration (seconds)."""
        with self.lock:
            self.active_anomalies[anomaly_type] = time.time() + duration
    
    def is_active(self, anomaly_type: str) -> bool:
        """Check if an anomaly type is currently active."""
        with self.lock:
            if anomaly_type not in self.active_anomalies:
                return False
            if time.time() > self.active_anomalies[anomaly_type]:
                del self.active_anomalies[anomaly_type]
                return False
            return True
    
    def get_active(self) -> list:
        """Get list of currently active anomalies."""
        with self.lock:
            now = time.time()
            active = []
            expired = []
            for atype, end_time in self.active_anomalies.items():
                if now < end_time:
                    active.append({
                        'type': atype,
                        'remaining_seconds': int(end_time - now)
                    })
                else:
                    expired.append(atype)
            for atype in expired:
                del self.active_anomalies[atype]
            return active

anomaly_state = AnomalyState()

# ============================================================================
# Traffic Simulation
# ============================================================================

def simulate_traffic():
    """
    Background thread that continuously generates realistic metrics.
    Runs every second; logic is shared with offline synthetic data
    (traffic_simulation_core.simulate_one_second).
    """
    SERVICE_UP.set(1)

    rng = random.Random()
    base_memory = new_base_memory(rng)
    MEMORY_USAGE.set(base_memory)

    def _is_anomaly(name: str, _dt: datetime) -> bool:
        return anomaly_state.is_active(name)

    while True:
        try:
            sample = simulate_one_second(datetime.now(), rng, base_memory, _is_anomaly)
            method = "GET"

            for e in sample.events:
                REQUEST_DURATION.labels(endpoint=e.endpoint).observe(e.latency)
                if e.is_error:
                    ERROR_COUNT.labels(
                        method=method,
                        endpoint=e.endpoint,
                        error_type=e.error_type,
                    ).inc()
                    REQUEST_COUNT.labels(
                        method=method, endpoint=e.endpoint, status="5xx"
                    ).inc()
                else:
                    REQUEST_COUNT.labels(
                        method=method, endpoint=e.endpoint, status="2xx"
                    ).inc()

            MEMORY_USAGE.set(sample.memory_bytes)
            CPU_SECONDS.inc(sample.cpu_seconds)
            SERVICE_UP.set(1)

        except Exception as ex:
            print(f"Error in traffic simulation: {ex}")

        time.sleep(1)


# ============================================================================
# API Endpoints
# ============================================================================

@app.route('/metrics')
def metrics():
    """Prometheus metrics endpoint."""
    return generate_latest(REGISTRY), 200, {'Content-Type': CONTENT_TYPE_LATEST}


@app.route('/health')
def health():
    """Health check endpoint."""
    return jsonify({
        'status': 'healthy',
        'timestamp': datetime.now().isoformat(),
        'active_anomalies': anomaly_state.get_active()
    })


@app.route('/anomaly', methods=['POST'])
def trigger_anomaly():
    """
    Trigger an anomaly injection.
    
    POST /anomaly
    {
        "type": "latency_spike" | "error_burst" | "memory_spike" | "traffic_drop",
        "duration": 300  // duration in seconds (default: 300 = 5 minutes)
    }
    """
    data = request.get_json() or {}
    
    anomaly_type = data.get('type')
    duration = data.get('duration', 300)  # Default 5 minutes
    
    valid_types = ['latency_spike', 'error_burst', 'memory_spike', 'traffic_drop']
    
    if not anomaly_type:
        return jsonify({
            'error': 'Missing required field: type',
            'valid_types': valid_types
        }), 400
    
    if anomaly_type not in valid_types:
        return jsonify({
            'error': f'Invalid anomaly type: {anomaly_type}',
            'valid_types': valid_types
        }), 400
    
    if not isinstance(duration, int) or duration < 1 or duration > 3600:
        return jsonify({
            'error': 'Duration must be an integer between 1 and 3600 seconds'
        }), 400
    
    anomaly_state.add_anomaly(anomaly_type, duration)
    
    return jsonify({
        'status': 'anomaly_triggered',
        'type': anomaly_type,
        'duration_seconds': duration,
        'message': f'Anomaly {anomaly_type} will be active for {duration} seconds'
    })


@app.route('/anomaly', methods=['GET'])
def get_anomalies():
    """Get currently active anomalies."""
    return jsonify({
        'active_anomalies': anomaly_state.get_active()
    })


@app.route('/anomaly/clear', methods=['POST'])
def clear_anomalies():
    """Clear all active anomalies."""
    with anomaly_state.lock:
        anomaly_state.active_anomalies.clear()
    return jsonify({
        'status': 'cleared',
        'message': 'All anomalies have been cleared'
    })


# ============================================================================
# Main
# ============================================================================

if __name__ == '__main__':
    # Start traffic simulation in background thread
    traffic_thread = threading.Thread(target=simulate_traffic, daemon=True)
    traffic_thread.start()
    
    print("Mock TV-over-IP Service starting...")
    print("Endpoints:")
    print("  GET  /metrics       - Prometheus metrics")
    print("  GET  /health        - Health check")
    print("  POST /anomaly       - Trigger anomaly")
    print("  GET  /anomaly       - Get active anomalies")
    print("  POST /anomaly/clear - Clear all anomalies")
    
    # Run Flask app
    app.run(host='0.0.0.0', port=8000, threaded=True)
