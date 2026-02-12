"""
Sliding window generation for time series anomaly detection.

Provides create_sequences() for training (multiple overlapping windows) and
create_single_window() for inference (single window from latest data).
"""

import numpy as np
import pandas as pd
from typing import Tuple


class WindowGenerator:
    """
    Sliding window generator for time series data.

    Training: creates multiple overlapping windows using stride.
    Inference: extracts a single window from the latest N points (stride ignored).
    """

    def __init__(self, window_size: int = 20, stride: int = 20):
        """
        Initialize the sliding window generator.

        Args:
            window_size: Number of timesteps per window (default: 20).
            stride: Step between windows for create_sequences(); ignored by create_single_window() (default: 20).
        """
        self.window_size = window_size
        self.stride = stride

    def create_sequences(self, data: pd.DataFrame,
                        target_columns: list = None) -> Tuple[np.ndarray, np.ndarray]:
        """
        Create sliding window sequences for training.

        Args:
            data: DataFrame with time series columns.
            target_columns: Columns to include. Defaults to all numeric except timestamp.

        Returns:
            Tuple of (X, y) where y equals X for autoencoder training.
        """
        if target_columns is None:
            target_columns = [col for col in data.columns 
                            if col != 'timestamp' and data[col].dtype in ['float64', 'int64']]
        
        values = data[target_columns].values
        X, y = [], []
        
        for i in range(0, len(values) - self.window_size + 1, self.stride):
            window = values[i:i + self.window_size]
            X.append(window)
            y.append(window)  # Autoencoder target equals input
        
        return np.array(X), np.array(y)
    
    def create_single_window(self, data: pd.DataFrame,
                            target_columns: list = None) -> np.ndarray:
        """
        Create a single window from the latest data (for inference).

        Extracts the last window_size points. If insufficient data, zero-pads
        at the start. Does not use stride.

        Args:
            data: DataFrame with current metrics.
            target_columns: Columns to include. Defaults to all numeric except timestamp.

        Returns:
            Array of shape (1, window_size, n_features) ready for inference.
        """
        if target_columns is None:
            target_columns = [col for col in data.columns 
                            if col != 'timestamp' and data[col].dtype in ['float64', 'int64']]
        
        values = data[target_columns].values
        
        # Zero-pad if insufficient data (may affect detection accuracy)
        if len(values) < self.window_size:
            padding = np.zeros((self.window_size - len(values), values.shape[1]))
            values = np.vstack([padding, values])
        
        return values[-self.window_size:].reshape(1, self.window_size, -1)
