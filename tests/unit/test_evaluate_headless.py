"""Unit test for evaluate_model headless mode."""

import os
import subprocess
import sys
from pathlib import Path

import pytest

# Project root (parent of tests/)
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent


def _model_files_exist():
    """Check if trained model files exist (required for evaluation)."""
    required = [
        "models/preprocessor.joblib",
        "models/lstm_autoencoder.weights.h5",
        "models/lstm_autoencoder_config.json",
        "models/anomaly_threshold.npy",
    ]
    return all((PROJECT_ROOT / f).exists() for f in required)


@pytest.mark.skipif(
    not _model_files_exist(),
    reason="Model files not found. Run 'python scripts/train.py' first.",
)
def test_evaluate_model_headless_completes():
    """evaluate_model.py --headless completes without blocking and produces PNG."""
    result = subprocess.run(
        [sys.executable, "scripts/evaluate_model.py", "--headless"],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert result.returncode == 0, f"stdout: {result.stdout}\nstderr: {result.stderr}"
    png_path = PROJECT_ROOT / "evaluation" / "model_evaluation.png"
    assert png_path.exists(), f"Expected {png_path} to exist after headless evaluation"
