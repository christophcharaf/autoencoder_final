---
name: troubleshooting-history
description: History of discovered issues and their fixes in the LSTM Autoencoder project. Use when debugging unexpected behavior, understanding why something was implemented a certain way, or when encountering familiar symptoms.
---

# Troubleshooting History

Known issues discovered and fixed during development. Check here first when debugging.

## Issue 1: Prometheus data loss on stack teardown

**Symptom**: All Prometheus data disappeared after `docker-compose down`.
**Cause**: No volume mount for Prometheus data directory.
**Fix**: Added `prometheus_data:/prometheus` volume in `docker-compose.yml`.

## Issue 2: Synthetic data distribution mismatch

**Symptom**: Model trained on synthetic data flagged all real Prometheus data as anomalous.
**Cause**: Synthetic data formulas did not match the mock service's actual output after PromQL aggregation (`rate()`, `histogram_quantile()`).
**Fix**: Derived correct formulas mathematically from mock service source code and verified against live Prometheus. Updated generators in both `train.py` and `inference.py`.

## Issue 3: Prometheus 11,000-point query limit

**Symptom**: `query_range` returned empty/error for 7-day queries at 30s step (20,160 points > 11K limit).
**Fix**: Added `_adjust_step_if_needed()` to `PrometheusClient` that auto-increases step when needed.

## Issue 4: StandardScaler generalization failure (critical)

**Symptom**: Model reconstruction error 1.97 vs threshold 0.41 on Prometheus data. Even fresh synthetic data got 100% false positive rate.
**Root cause**: StandardScaler memorizes training data's exact mean/std. Any new data (even same distribution, different random seed) with different `base_memory` or noise produces shifted z-scores. Model only learned one specific distribution.
**Diagnosis**: Tested same model with fresh scaler (fit on same test data) -- 1.1% FP rate. Confirmed scaler is the issue, not the model.
**Fix**: Implemented `fixed_minmax` scaler mode with predefined bounds in `DataPreprocessor`. Also changed stride from 20 to 1 (20x more training samples). Result: training loss 0.0021, Prometheus MSE 0.005, 80.5% headroom below threshold.

## Issue 5: Startup transient false anomaly

**Symptom**: ~9 minutes of anomaly detection after cold start.
**Cause**: `rate()[5m]` produces artificially low values until Prometheus has 5 minutes of scrapes.
**Status**: Known behavior, self-resolves. The anomaly detector correctly shows "RESOLVED" after the warm-up period.

## Issue 6: `get_tv_metrics` missing parameters

**Symptom**: `inference.py` passed `queries` parameter that `get_tv_metrics` didn't accept (latent TypeError).
**Fix**: Updated `get_tv_metrics` signature to accept `queries` and `step` parameters. Updated callers in both `train.py` and `inference.py`.

## Diagnostic commands

For the full troubleshooting journal with detailed analysis, see `TROUBLESHOOTING_JOURNAL.md` in the project root.
