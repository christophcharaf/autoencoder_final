---
name: ml-pipeline
description: Reference for the ML/anomaly detection pipeline including model architecture, preprocessing, training methodology, and threshold computation. Use when working on the model, debugging anomaly detection behavior, or tuning the pipeline.
---

# ML Pipeline Reference

## Training pipeline (`scripts/train.py`)

```
1. Load data: Prometheus (preferred) or synthetic fallback
2. Validate: min_rows >= window_size * 5
3. Preprocess: DataPreprocessor.fit_transform() -- adds temporal features + scales
4. Window: WindowGenerator.create_sequences(stride=1) -- overlapping windows
5. Split: temporal 80/20 (last 20% = validation)
6. Train: LSTM Autoencoder (30 epochs, batch_size=32, early stopping patience=10)
7. Threshold: 95th percentile of validation reconstruction errors
8. Save: weights, config JSON, preprocessor joblib, threshold npy
```

## Preprocessing details

**Scaler mode**: `fixed_minmax` (deterministic, data-independent)

Fixed bounds from `config/data.yaml`:
- request_rate: [0, 150], latency_p95: [0, 0.50], memory_usage: [0, 2B]
- error_rate: [0, 3.0], cpu_usage: [0, 0.15]
- Temporal features: [-1, 1] for sin/cos, [0, 1] for binary

**Why not StandardScaler**: StandardScaler memorizes training data distribution (mean/std). New data with different parameters produces shifted z-scores, causing 100% false positive rate. Fixed bounds eliminate this coupling.

## Synthetic data formulas

Daily pattern: `daily_factor = 0.5 + 0.4 * sin(2pi * (hour - 8) / 24)`

| Metric | Formula | Min (2 AM) | Max (2 PM) |
|--------|---------|------------|------------|
| request_rate | 125 * factor + N(0, 3) | ~12.5 | ~112.5 |
| latency_p95 | 0.22 * factor + 0.215 + N(0, 0.015) | ~0.24 | ~0.41 |
| memory_usage | base_memory + N(0, base*0.03) | constant | constant |
| error_rate | 2.5 * factor + N(0, 0.05) | ~0.25 | ~2.25 |
| cpu_usage | 0.125 * factor + N(0, 0.005) | ~0.013 | ~0.113 |

These formulas were derived from mathematical analysis of the mock service and verified against live Prometheus queries.

## Key gotchas

1. **Train/inference parity**: Both pipelines must use identical preprocessing. The saved `preprocessor.joblib` ensures this.
2. **Startup transient**: ~9 min of false anomaly after cold start (rate()[5m] warm-up).
3. **Window padding**: If fewer than window_size data points, zeros are padded. This degrades detection accuracy.
4. **Prometheus 11K limit**: Auto-adjusted in `PrometheusClient._adjust_step_if_needed()`.
