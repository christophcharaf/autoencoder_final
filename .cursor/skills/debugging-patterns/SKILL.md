# Debugging Patterns -- LSTM Autoencoder Anomaly Detection

## Diagnostic Decision Tree

```
Symptom reported
├── Container won't start / restart loop
│   ├── Check: docker logs <container> --since 5m
│   ├── Common: missing model files (FileNotFoundError on preprocessor.joblib or .weights.h5)
│   │   └── Fix: run training first -- docker-compose run --rm anomaly-detection python scripts/train.py
│   └── Common: import error after code change
│       └── Fix: check import paths, rebuild image if dependency changed
│
├── All data flagged as anomalous (100% false positives)
│   ├── Check: per-feature reconstruction error breakdown
│   ├── Common: scaler mismatch (model trained with StandardScaler, inference uses fixed_minmax or vice versa)
│   │   └── Fix: ensure preprocessor.joblib matches the scaler_type in config/data.yaml
│   ├── Common: rate()[5m] warm-up -- first ~9 minutes after stack start produce near-zero rates
│   │   └── Fix: wait for warm-up, self-resolves
│   └── Common: synthetic training distribution doesn't match real Prometheus data
│       └── Fix: compare formulas in train.py generate_synthetic_data vs mock_service/app.py
│
├── Empty Prometheus query results
│   ├── Check: curl -s --get "http://localhost:9090/api/v1/query" --data-urlencode "query=up"
│   ├── Common: Prometheus not running or mock-service not scraped yet
│   ├── Common: wrong query syntax (brackets not URL-encoded)
│   └── Common: time range exceeds 11,000-point limit
│       └── Fix: auto-adjustment in prometheus_client.py handles this, verify step parameter
│
└── Training crashes
    ├── Check: full traceback
    ├── Common: too few data points (len(df) < window_size * 5)
    │   └── Fix: min_rows validation already in train.py, verify Prometheus has enough history
    └── Common: shape mismatch in model (n_features changed)
        └── Fix: retrain from scratch, delete old model files
```

## Per-Feature MSE Analysis

When reconstruction error is high, break it down per feature to find the culprit:

```python
# Run inside the anomaly-detection container
docker exec tv-anomaly-detector python -c "
import numpy as np
from src.data.preprocessor import DataPreprocessor

preprocessor = DataPreprocessor()
preprocessor.load_scaler('models/preprocessor.joblib')

print('Scaler type:', preprocessor.scaler_type)
print('Features:', preprocessor.feature_columns)
print('Fixed bounds:', preprocessor.fixed_bounds)
"
```

## Known Historical Issues

| # | Issue | Root cause | File(s) fixed | Date |
|---|-------|-----------|--------------|------|
| 1 | Prometheus data lost on restart | No volume mount | docker-compose.yml | Feb 2026 |
| 2 | Synthetic data ranges wrong | Formulas didn't account for PromQL aggregation | train.py, inference.py | Feb 2026 |
| 3 | Query fails > 7 days | 11K-point limit | prometheus_client.py | Feb 2026 |
| 4 | get_tv_metrics TypeError | Missing queries/step params | prometheus_client.py | Feb 2026 |
| 5 | Training crash on few rows | No min_rows check | train.py | Feb 2026 |
| 6 | 100% false positives | StandardScaler memorized noise | preprocessor.py, data.yaml | Feb 2026 |
