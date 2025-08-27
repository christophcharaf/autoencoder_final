import numpy as np
import pandas as pd
from typing import Tuple

class WindowGenerator:
    """
    Generador de ventanas deslizantes para series temporales
    """
    
    def __init__(self, window_size: int = 20, stride: int = 20):
        self.window_size = window_size
        self.stride = stride
    
    def create_sequences(self, data: pd.DataFrame, 
                        target_columns: list = None) -> Tuple[np.ndarray, np.ndarray]:
        """
        Crea secuencias de ventanas deslizantes
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
        Crea una sola ventana desde los últimos datos (para inferencia)
        """
        if target_columns is None:
            target_columns = [col for col in data.columns 
                            if col != 'timestamp' and data[col].dtype in ['float64', 'int64']]
        
        values = data[target_columns].values
        
        if len(values) < self.window_size:
            padding = np.zeros((self.window_size - len(values), values.shape[1]))
            values = np.vstack([padding, values])
        
        return values[-self.window_size:].reshape(1, self.window_size, -1)
