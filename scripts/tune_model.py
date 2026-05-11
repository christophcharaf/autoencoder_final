#!/usr/bin/env python3
"""
Small, safe tuning loop for the LSTM autoencoder.

This script trains candidate models into evaluation/tuning_runs/ instead of
overwriting production artifacts in models/. Use it for architecture/window
experiments after threshold-only sweeps have been checked with evaluate_model.py.

Usage:
    python scripts/tune_model.py --quick
    python scripts/tune_model.py --history-hours 168 --epochs 10 --max-candidates 3
"""

import argparse
import csv
import json
import os
import sys
from copy import deepcopy
from datetime import datetime
from pathlib import Path

import numpy as np

sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'src'))
sys.path.append(os.path.dirname(__file__))

from data.preprocessor import DataPreprocessor
from data.synthetic_data import generate_synthetic_data, generate_test_data_with_anomalies
from data.windowing import WindowGenerator
from evaluate_model import _evaluate_at_threshold, _log_evaluation_summary
from models.lstm_autoencoder import LSTMAutoencoder
from utils.config import Config
from utils.logging import setup_logger


CANDIDATES = [
    {
        "id": "baseline",
        "window_size": 20,
        "encoder_layers": [64, 32, 16],
        "decoder_layers": [16, 32, 64],
        "dropout": 0.1,
        "learning_rate": 0.001,
    },
    {
        "id": "small_bottleneck",
        "window_size": 20,
        "encoder_layers": [32, 16, 8],
        "decoder_layers": [8, 16, 32],
        "dropout": 0.1,
        "learning_rate": 0.001,
    },
    {
        "id": "wide_bottleneck",
        "window_size": 20,
        "encoder_layers": [128, 64, 32],
        "decoder_layers": [32, 64, 128],
        "dropout": 0.1,
        "learning_rate": 0.001,
    },
    {
        "id": "window_30",
        "window_size": 30,
        "encoder_layers": [64, 32, 16],
        "decoder_layers": [16, 32, 64],
        "dropout": 0.1,
        "learning_rate": 0.001,
    },
    {
        "id": "dropout_02",
        "window_size": 20,
        "encoder_layers": [64, 32, 16],
        "decoder_layers": [16, 32, 64],
        "dropout": 0.2,
        "learning_rate": 0.001,
    },
]


class CandidateConfig:
    """Minimal Config-compatible wrapper for reporting candidate values."""

    def __init__(self, base_config: Config, candidate: dict):
        self.config = deepcopy(base_config.config)
        self.config.setdefault("windowing", {})["window_size"] = candidate["window_size"]
        self.config.setdefault("model", {}).setdefault("architecture", {})[
            "encoder_layers"
        ] = candidate["encoder_layers"]
        self.config["model"]["architecture"]["decoder_layers"] = candidate["decoder_layers"]
        self.config["model"]["architecture"]["dropout"] = candidate["dropout"]
        self.config["model"].setdefault("hyperparameters", {})[
            "learning_rate"
        ] = candidate["learning_rate"]

    def get(self, key: str, default=None):
        value = self.config
        for part in key.split("."):
            if isinstance(value, dict) and part in value:
                value = value[part]
            else:
                return default
        return value


def _save_candidate_artifacts(
    run_dir: Path,
    model: LSTMAutoencoder,
    preprocessor: DataPreprocessor,
    threshold: float,
    candidate: dict,
    training_history: dict,
) -> None:
    run_dir.mkdir(parents=True, exist_ok=True)
    model.save(str(run_dir / "lstm_autoencoder.h5"))
    preprocessor.save_scaler(str(run_dir / "preprocessor.joblib"))
    np.save(run_dir / "anomaly_threshold.npy", threshold)
    with open(run_dir / "candidate_config.json", "w") as f:
        json.dump(
            {
                "candidate": candidate,
                "threshold": threshold,
                "training_history": training_history,
            },
            f,
            indent=2,
        )


def _append_tuning_result(row: dict, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    file_exists = path.exists()
    with open(path, "a", newline="") as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=list(row.keys()))
        if not file_exists:
            writer.writeheader()
        writer.writerow(row)


def _window_labels(true_labels: np.ndarray, window_size: int, stride: int) -> np.ndarray:
    labels = []
    n_windows = len(range(0, len(true_labels) - window_size + 1, stride))
    for i in range(n_windows):
        start_idx = i * stride
        end_idx = start_idx + window_size
        labels.append(int(np.any(true_labels[start_idx:end_idx])))
    return np.array(labels)


def run_tuning(args) -> list:
    logger = setup_logger()
    base_config = Config()

    history_hours = 24 if args.quick else args.history_hours
    epochs = 3 if args.quick else args.epochs
    max_candidates = args.max_candidates or len(CANDIDATES)
    candidates = CANDIDATES[:max_candidates]

    logger.info("=== Starting model tuning loop ===")
    logger.info("Training history hours: %s", history_hours)
    logger.info("Epochs per candidate: %s", epochs)
    logger.info("Candidates: %s", [c["id"] for c in candidates])

    train_df = generate_synthetic_data(history_hours=history_hours, seed=args.seed)
    test_df, true_labels = generate_test_data_with_anomalies(
        history_hours=args.test_hours,
        seed=args.test_seed,
    )

    scaler_type = base_config.get("data.features.preprocessing.normalization", "fixed_minmax")
    temporal_features = base_config.get("data.features.temporal", {})
    fixed_bounds = base_config.get("data.features.preprocessing.fixed_bounds", {})
    stride = base_config.get("windowing.stride", 1)
    threshold_percentile = args.threshold_percentile
    validation_split = base_config.get("model.training.validation_split", 0.2)
    batch_size = args.batch_size or base_config.get("model.training.batch_size", 256)
    patience = args.patience or base_config.get("model.training.patience", 10)

    run_root = Path("evaluation") / "tuning_runs" / datetime.now().strftime("%Y%m%d_%H%M%S")
    results = []

    for candidate in candidates:
        candidate_id = candidate["id"]
        logger.info("=== Candidate: %s ===", candidate_id)

        preprocessor = DataPreprocessor(
            scaler_type=scaler_type,
            temporal_features=temporal_features,
            fixed_bounds=fixed_bounds,
        )
        train_processed = preprocessor.fit_transform(train_df)
        window_size = candidate["window_size"]
        windower = WindowGenerator(window_size=window_size, stride=stride)
        X, _ = windower.create_sequences(train_processed)

        split_idx = int((1 - validation_split) * len(X))
        X_train, X_val = X[:split_idx], X[split_idx:]

        model = LSTMAutoencoder(
            input_shape=(X_train.shape[1], X_train.shape[2]),
            encoder_layers=candidate["encoder_layers"],
            decoder_layers=candidate["decoder_layers"],
            dropout=candidate["dropout"],
            learning_rate=candidate["learning_rate"],
            optimizer=base_config.get("model.hyperparameters.optimizer", "adam"),
        )
        history = model.train(
            X_train=X_train,
            X_val=X_val,
            epochs=epochs,
            batch_size=batch_size,
            early_stopping=True,
            patience=patience,
            verbose=args.verbose,
        )

        validation_errors = model.compute_reconstruction_error(X_val)
        threshold = float(np.percentile(validation_errors, threshold_percentile))

        test_processed = preprocessor.transform(test_df)
        X_test, _ = windower.create_sequences(test_processed)
        y_true = _window_labels(true_labels, window_size, stride)
        reconstruction_errors = model.compute_reconstruction_error(X_test)
        window_timestamps = np.array(
            [test_df["timestamp"].iloc[i * stride] for i in range(len(X_test))]
        )

        reporting_config = CandidateConfig(base_config, candidate)
        summary = _evaluate_at_threshold(
            threshold,
            threshold_percentile,
            reconstruction_errors,
            y_true,
            window_timestamps,
            reporting_config,
            window_size,
            stride,
        )
        _log_evaluation_summary(summary, logger, f"=== TUNING RESULT: {candidate_id} ===")

        run_dir = run_root / candidate_id
        _save_candidate_artifacts(
            run_dir,
            model,
            preprocessor,
            threshold,
            candidate,
            history,
        )

        row = {
            "run_timestamp": datetime.now().isoformat(timespec="seconds"),
            "candidate_id": candidate_id,
            "run_dir": str(run_dir),
            "history_hours": history_hours,
            "epochs": epochs,
            "window_size": window_size,
            "encoder_layers": candidate["encoder_layers"],
            "decoder_layers": candidate["decoder_layers"],
            "dropout": candidate["dropout"],
            "learning_rate": candidate["learning_rate"],
            "threshold_percentile": threshold_percentile,
            "threshold": summary["threshold"],
            "accuracy": summary["accuracy"],
            "precision": summary["precision"],
            "recall": summary["recall"],
            "f1_score": summary["f1_score"],
            "tn": int(summary["confusion_matrix"].ravel()[0]),
            "fp": int(summary["confusion_matrix"].ravel()[1]),
            "fn": int(summary["confusion_matrix"].ravel()[2]),
            "tp": int(summary["confusion_matrix"].ravel()[3]),
        }
        _append_tuning_result(row, run_root / "tuning_results.csv")
        results.append(row)

    logger.info("Tuning results saved to %s", run_root / "tuning_results.csv")
    return results


def main():
    parser = argparse.ArgumentParser(description="Run safe model tuning candidates")
    parser.add_argument("--quick", action="store_true", help="Use 24h training data and 3 epochs")
    parser.add_argument("--history-hours", type=int, default=168)
    parser.add_argument("--test-hours", type=int, default=24)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--test-seed", type=int, default=123)
    parser.add_argument("--epochs", type=int, default=10)
    parser.add_argument("--batch-size", type=int, default=None)
    parser.add_argument("--patience", type=int, default=None)
    parser.add_argument("--threshold-percentile", type=float, default=99.5)
    parser.add_argument("--max-candidates", type=int, default=None)
    parser.add_argument("--verbose", type=int, default=1)
    args = parser.parse_args()
    run_tuning(args)


if __name__ == "__main__":
    main()
