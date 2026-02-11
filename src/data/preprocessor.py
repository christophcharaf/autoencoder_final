"""
Data Preprocessor for LSTM Autoencoder

This module handles data preprocessing for the anomaly detection model:
    - Temporal feature engineering (cyclical hour encoding, day of week, etc.)
    - Data normalization (StandardScaler or MinMaxScaler)
    - Scaler persistence for inference

The preprocessor ensures consistent data transformation between training
and inference phases by saving/loading the fitted scaler.
"""

import pandas as pd
import numpy as np
from sklearn.preprocessing import StandardScaler, MinMaxScaler
from typing import Tuple, Optional, Dict
import joblib


class DataPreprocessor:
    """
    Data preprocessor for the LSTM Autoencoder anomaly detection model.
    
    Handles feature engineering and normalization of time series data.
    Temporal features use cyclical encoding (sin/cos) to preserve the
    circular nature of time (e.g., hour 23 is close to hour 0).
    
    Attributes:
        scaler_type: Type of scaler to use ('standard' or 'minmax')
        scaler: Fitted sklearn scaler instance
        feature_columns: List of feature column names (excludes timestamp)
        temporal_features: Dict controlling which temporal features to add
    
    Example:
        >>> preprocessor = DataPreprocessor(scaler_type='standard')
        >>> df_processed = preprocessor.fit_transform(df)
        >>> preprocessor.save_scaler('models/preprocessor.joblib')
    """
    
    def __init__(self, scaler_type: str = 'standard', temporal_features: Dict = None):
        """
        Initialize the data preprocessor.
        
        Args:
            scaler_type: Normalization method - 'standard' (z-score) or 'minmax' (0-1)
            temporal_features: Dict controlling which temporal features to generate.
                             Keys: hour_sin, hour_cos, day_of_week, is_weekend, is_night
        """
        self.scaler_type = scaler_type
        self.scaler = None
        self.feature_columns = None
        
        # Default temporal feature settings (all enabled)
        self.temporal_features = temporal_features or {
            'hour_sin': True,
            'hour_cos': True,
            'day_of_week': True,
            'is_weekend': True,
            'is_night': True
        }
        
    def fit_transform(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Fit the preprocessor on training data and transform it.
        
        This method should be called once during training to:
            1. Add temporal features based on configuration
            2. Identify numeric feature columns
            3. Fit the scaler on the training data distribution
            4. Transform the data using the fitted scaler
        
        Args:
            df: Raw DataFrame with 'timestamp' column and metric columns
        
        Returns:
            pd.DataFrame: Preprocessed DataFrame with normalized features
        """
        df_processed = df.copy()
        
        # Add temporal features (hour encoding, day of week, etc.)
        df_processed = self._add_temporal_features(df_processed)
        
        # Identify numeric columns for normalization (exclude timestamp)
        numeric_cols = df_processed.select_dtypes(include=[np.number]).columns
        self.feature_columns = [col for col in numeric_cols if col != 'timestamp']
        
        # Initialize scaler based on configuration
        if self.scaler_type == 'standard':
            self.scaler = StandardScaler()  # Z-score normalization (mean=0, std=1)
        elif self.scaler_type == 'minmax':
            self.scaler = MinMaxScaler()    # Scale to [0, 1] range
        
        # Fit scaler and transform data
        if len(self.feature_columns) > 0:
            df_processed[self.feature_columns] = self.scaler.fit_transform(
                df_processed[self.feature_columns]
            )
        
        return df_processed
    
    def transform(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Transform new data using the already-fitted scaler.
        
        This method should be called during inference to transform new data
        using the same normalization parameters learned during training.
        
        Args:
            df: Raw DataFrame with 'timestamp' column and metric columns
        
        Returns:
            pd.DataFrame: Preprocessed DataFrame with normalized features
        
        Raises:
            ValueError: If the preprocessor has not been fitted yet
        """
        if self.scaler is None:
            raise ValueError("Preprocessor must be fitted first. Call fit_transform() or load_scaler().")
        
        df_processed = df.copy()
        df_processed = self._add_temporal_features(df_processed)
        
        if len(self.feature_columns) > 0:
            df_processed[self.feature_columns] = self.scaler.transform(
                df_processed[self.feature_columns]
            )
        
        return df_processed
    
    def _add_temporal_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Add temporal features based on configuration settings.
        
        Temporal features help the model learn time-dependent patterns:
            - hour_sin/cos: Cyclical encoding of hour (0-23)
            - dayofweek_sin/cos: Cyclical encoding of day of week (0-6)
            - is_weekend: Binary flag for Saturday/Sunday
            - is_night: Binary flag for night hours (22:00-06:00)
        
        Args:
            df: DataFrame with 'timestamp' column
        
        Returns:
            pd.DataFrame: DataFrame with added temporal feature columns
        """
        if 'timestamp' not in df.columns:
            return df
        
        df = df.copy()
        df['timestamp'] = pd.to_datetime(df['timestamp'])
        
        # Extract hour for multiple features
        hour = df['timestamp'].dt.hour
        
        # Codificación cíclica de hora
        if self.temporal_features.get('hour_sin', True):
            df['hour_sin'] = np.sin(2 * np.pi * hour / 24)
        
        if self.temporal_features.get('hour_cos', True):
            df['hour_cos'] = np.cos(2 * np.pi * hour / 24)
        
        # Día de la semana
        if self.temporal_features.get('day_of_week', True):
            dayofweek = df['timestamp'].dt.dayofweek
            # Encode as sin/cos for cyclical nature
            df['dayofweek_sin'] = np.sin(2 * np.pi * dayofweek / 7)
            df['dayofweek_cos'] = np.cos(2 * np.pi * dayofweek / 7)
        
        # Is weekend flag
        if self.temporal_features.get('is_weekend', True):
            df['is_weekend'] = (df['timestamp'].dt.dayofweek >= 5).astype(int)
        
        # Is night flag (night hours: 22:00 - 06:00)
        if self.temporal_features.get('is_night', True):
            df['is_night'] = ((hour >= 22) | (hour < 6)).astype(int)
        
        return df
    
    def save_scaler(self, path: str):
        """
        Save the fitted preprocessor to disk.
        
        Saves all state needed to transform new data consistently:
            - Fitted scaler (with learned mean/std or min/max)
            - Feature column names
            - Scaler type and temporal feature configuration
        
        Args:
            path: File path for saving (typically .joblib extension)
        """
        joblib.dump({
            'scaler': self.scaler,
            'feature_columns': self.feature_columns,
            'scaler_type': self.scaler_type,
            'temporal_features': self.temporal_features
        }, path)
    
    def load_scaler(self, path: str):
        """
        Load a previously saved preprocessor from disk.
        
        Restores all state needed to transform new data using the same
        normalization parameters that were learned during training.
        
        Args:
            path: File path to load from
        """
        data = joblib.load(path)
        self.scaler = data['scaler']
        self.feature_columns = data['feature_columns']
        self.scaler_type = data['scaler_type']
        # Handle backward compatibility for older saved preprocessors
        self.temporal_features = data.get('temporal_features', {
            'hour_sin': True,
            'hour_cos': True,
            'day_of_week': True,
            'is_weekend': True,
            'is_night': True
        })
