import numpy as np
import pandas as pd
from typing import Tuple

class WindowGenerator:
    """
    Generador de ventanas deslizantes para series temporales.
    
    Durante el entrenamiento, crea múltiples ventanas deslizantes usando el parámetro
    'stride' para controlar el solapamiento entre ventanas.
    
    Durante la inferencia, solo extrae una ventana de los últimos N puntos de datos
    (donde N = window_size), ignorando el parámetro stride.
    
    Args:
        window_size: Número de timesteps en cada ventana
        stride: Paso entre ventanas durante entrenamiento (solo para create_sequences)
    """
    
    def __init__(self, window_size: int = 20, stride: int = 20):
        self.window_size = window_size
        self.stride = stride
    
    def create_sequences(self, data: pd.DataFrame, 
                        target_columns: list = None) -> Tuple[np.ndarray, np.ndarray]:
        """
        Crea secuencias de ventanas deslizantes para entrenamiento.
        
        Utiliza el parámetro 'stride' para generar múltiples ventanas:
        - stride = window_size: ventanas no solapadas (uso actual)
        - stride < window_size: ventanas solapadas (más ejemplos de entrenamiento)
        
        Args:
            data: DataFrame con series temporales
            target_columns: Columnas a incluir en las ventanas
            
        Returns:
            Tuple de (X, y) donde y = X para autoencoders
        """
        if target_columns is None:
            target_columns = [col for col in data.columns 
                            if col != 'timestamp' and data[col].dtype in ['float64', 'int64']]
        
        values = data[target_columns].values
        X, y = [], []
        
        for i in range(0, len(values) - self.window_size + 1, self.stride):
            window = values[i:i + self.window_size]
            X.append(window)
            y.append(window)  # Para autoencoder, target = input
        
        return np.array(X), np.array(y)
    
    def create_single_window(self, data: pd.DataFrame, 
                           target_columns: list = None) -> np.ndarray:
        """
        Crea una sola ventana desde los últimos datos (para inferencia).
        
        IMPORTANTE: Este método NO usa el parámetro 'stride'. Siempre extrae
        los últimos window_size puntos de datos disponibles.
        
        Si no hay suficientes datos (len(data) < window_size), rellena con ceros
        al inicio. Esto puede reducir la precisión de detección, por lo que es
        importante que inference_minutes proporcione suficientes datos:
        
        inference_minutes × 2 samples/min ≥ window_size
        
        Args:
            data: DataFrame con métricas actuales
            target_columns: Columnas a incluir en la ventana
            
        Returns:
            Array de forma (1, window_size, n_features) listo para inferencia
        """
        if target_columns is None:
            target_columns = [col for col in data.columns 
                            if col != 'timestamp' and data[col].dtype in ['float64', 'int64']]
        
        values = data[target_columns].values
        
        # Zero-padding si no hay suficientes datos
        # ADVERTENCIA: El padding puede afectar la detección de anomalías
        if len(values) < self.window_size:
            padding = np.zeros((self.window_size - len(values), values.shape[1]))
            values = np.vstack([padding, values])
        
        return values[-self.window_size:].reshape(1, self.window_size, -1)
