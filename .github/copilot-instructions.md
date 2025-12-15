# Copilot Instructions for Autoencoder Anomaly Detection

## Project Overview

This is a **TV-over-IP anomaly detection system** using LSTM Autoencoders. The system collects metrics from Prometheus, detects anomalous patterns in real-time, and sends alerts via Opsgenie. It's a production-ready MVP with synthetic data support for development.

**Key insight**: All components are loosely coupled via config-driven initialization. Changes should follow the Config → Component → Pipeline pattern.

## Critical Architecture

### Data Flow Pipeline (train → inference)

```
Prometheus/Synthetic Data → Preprocessor (StandardScaler) → WindowGenerator 
  → LSTM Autoencoder → AnomalyDetector → Opsgenie/Grafana
```

### Four Main Modules (src/)

1. **data/** - Ingestion & preprocessing
   - `prometheus_client.py`: Fetches metrics via Prometheus API
   - `preprocessor.py`: StandardScaler fitted on training data, reused in inference
   - `windowing.py`: Creates sliding windows for time-series modeling
   
2. **models/** - LSTM Autoencoder
   - `lstm_autoencoder.py`: Keras-based encoder-decoder architecture
   - All LSTM decoder layers MUST have `return_sequences=True` (common source of bugs)
   
3. **alerting/** - Detection & notifications
   - `detector.py`: Anomaly scoring via reconstruction error thresholds
   - `opsgenie_client.py`: Sends alerts with 5-minute throttling
   - `grafana_links.py`: Generates contextual dashboard links
   
4. **utils/** - Configuration & logging
   - `config.py`: YAML-based with environment variable overrides (critical for deployment)
   - Loads all `config/*.yaml` files and merges with env vars

### Data Flows to Know

**Training** (scripts/train.py):
- Generates 7 days of synthetic data (20,160 points at 30s intervals)
- Fits preprocessor on full dataset → saves to `models/preprocessor.joblib`
- Creates sequences with window_size=20, stride=20
- Trains model with 80/20 split, early stopping on val_loss

**Inference** (scripts/inference.py):
- Loads fitted preprocessor (MUST reload to use same scale)
- Queries Prometheus in 5-min intervals
- Computes reconstruction error on sliding windows
- Throttles alerts to max 1 per 5 minutes

## Developer Workflows

### Running Training
```bash
python scripts/train.py
```
Outputs: `models/lstm_autoencoder_config.json`, `models/preprocessor.joblib`

**Development shortcut**: Uses synthetic data if `PROMETHEUS_URL` env var is missing.

### Running Inference  
```bash
python scripts/inference.py
```
Infinite loop (handle with SIGTERM). Requires trained model + fitted preprocessor in `models/`.

### Configuration Strategy

Never hardcode values—use `Config` class:
```python
config = Config()
batch_size = config.get('model.training.batch_size', default=32)
threshold = config.get('alerting.threshold.percentile', default=95)
```

Override via env vars (highest priority):
```bash
export PROMETHEUS_URL=http://localhost:9090
export OPSGENIE_API_KEY=xxx
python scripts/inference.py
```

## Code Patterns & Conventions

### Preprocessing Pattern
The `DataPreprocessor` must be fitted on training data only:
```python
preprocessor = DataPreprocessor(scaler_type='standard')
X_train_scaled = preprocessor.fit_transform(train_data)  # Learn normalization
preprocessor.save_scaler('models/preprocessor.joblib')

# Later in inference:
preprocessor = DataPreprocessor()
preprocessor.load_scaler('models/preprocessor.joblib')
X_test_scaled = preprocessor.transform(test_data)  # Apply saved scale
```
**Bug prevention**: Never fit preprocessor on test/inference data.

### LSTM Return Sequences Rule
All LSTM layers in decoder MUST use `return_sequences=True` except when outputting final features:
```python
# ✅ CORRECT - all have return_sequences=True
for units in decoder_layers:
    x = layers.LSTM(units, return_sequences=True)(x)
x = layers.TimeDistributed(layers.Dense(n_features))(x)

# ❌ WRONG - will cause shape mismatches
x = layers.LSTM(units, return_sequences=False)(x)  # loses temporal dimension
```

### Alert Throttling
The inference service enforces minimum 5-minute intervals between alerts to avoid alert fatigue:
```python
if last_alert_time is None or (now - last_alert_time).total_seconds() > 300:
    opsgenie_client.create_alert(...)
    last_alert_time = now
```

### Config Loading Order (config.py)
1. Load all `config/*.yaml` files
2. Apply environment variable overrides (highest priority)
3. Fall back to hardcoded defaults if config files missing

## Key Files to Know

- [config/model.yaml](../config/model.yaml) - Model architecture & training hyperparameters
- [config/data.yaml](../config/data.yaml) - Prometheus URL & data source config
- [config/alerting.yaml](../config/alerting.yaml) - Threshold method & alert config
- [scripts/train.py](../scripts/train.py) - Full training pipeline
- [scripts/inference.py](../scripts/inference.py) - Real-time detection loop
- [src/models/lstm_autoencoder.py](../src/models/lstm_autoencoder.py) - Model architecture
- [src/data/preprocessor.py](../src/data/preprocessor.py) - Data scaling & feature engineering
- [src/utils/config.py](../src/utils/config.py) - Configuration loader

## Environment Setup

**Dependencies**: TensorFlow 2.x, Keras, pandas, numpy, scikit-learn, prometheus-api-client  
**Python version**: 3.8+ (conda env: `autoencoder`)

Install via:
```bash
conda env create -f requirements.yml
conda activate autoencoder
```

## Common Pitfalls

1. **Preprocessor mismatch**: Loading different preprocessor in inference than training → scaling inconsistency
2. **LSTM shape errors**: Forgetting `return_sequences=True` in decoder layers
3. **Missing models directory**: Ensure `models/` exists before saving/loading
4. **Prometheus connectivity**: Falls back to synthetic data—check `PROMETHEUS_URL` env var
5. **Alert fatigue**: Opsgenie throttling set to 5 minutes (edit in `inference.py`)

## Adding Features

**New metric source?** Add client in `src/data/prometheus_client.py`, update `config/data.yaml`  
**New preprocessing step?** Add method in `src/data/preprocessor.py` and call in `fit_transform()`  
**New alert channel?** Create client in `src/alerting/`, inherit notification pattern from `OpsgenieClient`  
**New detector?** Implement in `src/alerting/detector.py` using reconstruction error or other metrics
