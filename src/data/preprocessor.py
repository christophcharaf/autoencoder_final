import pandas as pd
import numpy as np
from sklearn.preprocessing import StandardScaler, MinMaxScaler
from typing import Tuple, Optional
import joblib

class DataPreprocessor:
    """
    Preprocesamiento de datos para el modelo LSTM Autoencoder
    """
    
    def __init__(self, scaler_type: str = 'standard'):
        self.scaler_type = scaler_type
        self.scaler = None
        self.feature_columns = None
        
    def fit_transform(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Ajusta el preprocesador y transforma los datos
        """
        df_processed = df.copy()
        
        # Feature engineering básico
        df_processed = self._add_temporal_features(df_processed)
        
        # Seleccionar solo columnas numéricas (excluir timestamp)
        numeric_cols = df_processed.select_dtypes(include=[np.number]).columns
        self.feature_columns = [col for col in numeric_cols if col != 'timestamp']
        
        # Normalización
        if self.scaler_type == 'standard':
            self.scaler = StandardScaler()
        elif self.scaler_type == 'minmax':
            self.scaler = MinMaxScaler()
        
        # Ajustar y transformar
        if len(self.feature_columns) > 0:
            df_processed[self.feature_columns] = self.scaler.fit_transform(
                df_processed[self.feature_columns]
            )
        
        return df_processed
    
    def transform(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Transforma nuevos datos usando scaler ya ajustado
        """
        if self.scaler is None:
            raise ValueError("Preprocessor must be fitted first")
        
        df_processed = df.copy()
        df_processed = self._add_temporal_features(df_processed)
        
        if len(self.feature_columns) > 0:
            df_processed[self.feature_columns] = self.scaler.transform(
                df_processed[self.feature_columns]
            )
        
        return df_processed
    
    def _add_temporal_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Agrega features temporales básicos
        """
        if 'timestamp' not in df.columns:
            return df
        
        df = df.copy()
        df['timestamp'] = pd.to_datetime(df['timestamp'])
        
        # Codificación cíclica de hora
        df['hour'] = df['timestamp'].dt.hour
        df['hour_sin'] = np.sin(2 * np.pi * df['hour'] / 24)
        df['hour_cos'] = np.cos(2 * np.pi * df['hour'] / 24)
        
        # Día de la semana  
        df['dayofweek'] = df['timestamp'].dt.dayofweek
        df['is_weekend'] = (df['dayofweek'] >= 5).astype(int)
        
        # Eliminar columnas temporales intermedias
        df.drop(['hour', 'dayofweek'], axis=1, inplace=True)
        
        return df
    
    def save_scaler(self, path: str):
        """Guarda el scaler entrenado"""
        joblib.dump({
            'scaler': self.scaler,
            'feature_columns': self.feature_columns,
            'scaler_type': self.scaler_type
        }, path)
    
    def load_scaler(self, path: str):
        """Carga scaler previamente entrenado"""
        data = joblib.load(path)
        self.scaler = data['scaler']
        self.feature_columns = data['feature_columns']
        self.scaler_type = data['scaler_type']
