---
name: project-architecture
description: Reference for the LSTM Autoencoder anomaly detection project structure, component responsibilities, and data flow. Use when navigating the codebase, understanding how components connect, or onboarding to the project.
---

# Project Architecture

## Data flow

```
Prometheus (scrapes mock-service every 30s)
    |
    v
PrometheusClient.get_tv_metrics()    [src/data/prometheus_client.py]
    |  -- PromQL queries from config/data.yaml
    |  -- Auto-adjusts step if >11K points
    v
Raw DataFrame (timestamp, request_rate, latency_p95, memory_usage, error_rate, cpu_usage)
    |
    v
DataPreprocessor.transform()          [src/data/preprocessor.py]
    |  -- Adds temporal features (hour_sin/cos, dayofweek_sin/cos, is_weekend, is_night)
    |  -- Scales to [0,1] using fixed_minmax bounds from config
    v
Scaled DataFrame (11 features)
    |
    v
WindowGenerator.create_single_window() [src/data/windowing.py]  (inference)
WindowGenerator.create_sequences()      [src/data/windowing.py]  (training)
    |
    v
numpy array shape (batch, 20, 11)
    |
    v
LSTMAutoencoder.predict()             [src/models/lstm_autoencoder.py]
    |  -- Encoder: 64 -> 32 -> 16
    |  -- Decoder: 16 -> 32 -> 64
    |  -- Output: TimeDistributed Dense
    v
Reconstruction error (MSE per window)
    |
    v
AnomalyDetector.detect()              [src/alerting/detector.py]
    |  -- Compare MSE to saved threshold
    v
Alert pipeline (dedup, Opsgenie, Grafana links)  [scripts/inference.py]
```

## Config hierarchy

All config loaded via `src/utils/config.py` using dot-notation:

| File | Key prefix | Controls |
|------|-----------|----------|
| `config/data.yaml` | `data.*` | Prometheus URL, metric queries, preprocessing, fixed_bounds, collection params |
| `config/model.yaml` | `model.*` | Architecture, hyperparams, training settings |
| `config/windowing.yaml` | `windowing.*` | window_size, stride |
| `config/alerting.yaml` | `alerting.*` | Threshold method, rate limiting, Opsgenie, Grafana |

## Docker services (dev profile)

| Service | Container | Port | Purpose |
|---------|-----------|------|---------|
| mock-service | mock-tv-service | 8000 | Simulated TV-over-IP with anomaly injection |
| prometheus | prometheus | 9090 | Metrics storage, scrapes mock-service |
| anomaly-detection | tv-anomaly-detector | 8080 | Runs inference.py |
| grafana | grafana | 3000 | Dashboards |
