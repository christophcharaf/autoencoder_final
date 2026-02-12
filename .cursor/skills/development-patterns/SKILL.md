---
name: development-patterns
description: Development conventions and patterns for the LSTM Autoencoder project. Use when implementing features, making code changes, or reviewing development practices in this codebase.
---

# Development Patterns

## Config-driven development

All tunable values live in `config/*.yaml`. Load via the `Config` class:

```python
from utils.config import Config
config = Config()

# Dot-notation access
url = config.get('data.prometheus.url')
window_size = config.get('windowing.window_size', 20)  # with default
queries = config.get('data.metrics.queries', None)
```

**Never hardcode** values that could change between environments or experiments.

## Train/inference parity checklist

When modifying data processing, ensure both pipelines stay in sync:

- [ ] `scripts/train.py` -- training data path
- [ ] `scripts/inference.py` -- inference data path + synthetic fallback
- [ ] `src/data/preprocessor.py` -- shared preprocessor (saved/loaded via joblib)
- [ ] `config/data.yaml` -- shared config source

## Docker workflow

```bash
# Start dev stack
docker-compose --profile dev up -d

# Rebuild after code changes
docker-compose build anomaly-detection

# Run training in container
docker-compose run --rm anomaly-detection python scripts/train.py

# Check inference logs
docker logs tv-anomaly-detector --since 5m

# Inject anomaly for testing
curl -X POST http://localhost:8000/anomaly -H "Content-Type: application/json" -d '{"type": "latency_spike", "duration": 120}'

# Stop stack (data persists in prometheus_data volume)
docker-compose --profile dev down
```

## Testing anomaly detection

The mock service at `localhost:8000` supports anomaly injection:

| Type | Duration | Effect |
|------|----------|--------|
| `latency_spike` | 1-3600s | Latency jumps to 2-10s |
| `error_burst` | 1-3600s | Error rate jumps to 30% |
| `memory_spike` | 1-3600s | Memory jumps to 3-4GB |
| `traffic_drop` | 1-3600s | 90% traffic reduction |

Note: `rate()[5m]` smoothing means anomalies take ~5 min to fully appear in Prometheus and ~5 min to clear after stopping.

## File naming conventions

- Models: `models/lstm_autoencoder.weights.h5`, `models/lstm_autoencoder_config.json`
- Preprocessor: `models/preprocessor.joblib`
- Threshold: `models/anomaly_threshold.npy`
- Config: `config/{domain}.yaml` (data, model, windowing, alerting)
