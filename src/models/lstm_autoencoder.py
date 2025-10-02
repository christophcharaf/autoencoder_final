import tensorflow as tf
from tensorflow import keras
from keras import layers
import numpy as np
from typing import List, Tuple

class LSTMAutoencoder:
    """
    Autoencoder basado en LSTM para detección de anomalías
    """
    
    def __init__(self, input_shape: Tuple[int, int], 
                 encoder_layers: List[int] = [64, 32, 16],
                 decoder_layers: List[int] = [16, 32, 64],
                 dropout: float = 0.1):
        
        self.input_shape = input_shape
        self.encoder_layers = encoder_layers
        self.decoder_layers = decoder_layers
        self.dropout = dropout
        self.model = None
        self.encoder = None
        
        self._build_model()
    
    def _build_model(self):
        """Construye la arquitectura del autoencoder"""
        
        # Input layer
        inputs = keras.Input(shape=self.input_shape)
        
        # Encoder
        x = inputs
        for i, units in enumerate(self.encoder_layers[:-1]):
            x = layers.LSTM(units, return_sequences=True, 
                          name=f'encoder_lstm_{i}')(x)
            x = layers.Dropout(self.dropout)(x)
        
        # Latent representation
        latent = layers.LSTM(self.encoder_layers[-1], return_sequences=False, 
                           name='latent')(x)
        
        # Repeat latent vector para decoder
        x = layers.RepeatVector(self.input_shape[0])(latent)
        
        # Decoder - TODAS las capas LSTM deben tener return_sequences=True
        for i, units in enumerate(self.decoder_layers):
            x = layers.LSTM(units, return_sequences=True,  # ✅ SIEMPRE True
                          name=f'decoder_lstm_{i}')(x)
            x = layers.Dropout(self.dropout)(x)
        
        # Output layer - Usar TimeDistributed para aplicar Dense a cada timestep
        outputs = layers.TimeDistributed(
            layers.Dense(self.input_shape[1], activation='linear')
        )(x)
        
        # Compilar modelo
        self.model = keras.Model(inputs=inputs, outputs=outputs, name='lstm_autoencoder')
        self.model.compile(optimizer='adam', loss='mse', metrics=['mae'])
        
        # Crear encoder independiente
        self.encoder = keras.Model(inputs=inputs, outputs=latent, name='encoder')
    
    def train(self, X_train: np.ndarray, X_val: np.ndarray = None, 
              epochs: int = 50, batch_size: int = 32, verbose: int = 1) -> dict:
        """
        Entrena el autoencoder
        """
        callbacks = [
            keras.callbacks.EarlyStopping(
                monitor='val_loss' if X_val is not None else 'loss',
                patience=10,
                restore_best_weights=True
            ),
            keras.callbacks.ReduceLROnPlateau(
                monitor='val_loss' if X_val is not None else 'loss',
                factor=0.5,
                patience=5,
                min_lr=1e-7
            )
        ]
        
        validation_data = (X_val, X_val) if X_val is not None else None
        
        history = self.model.fit(
            X_train, X_train,
            validation_data=validation_data,
            epochs=epochs,
            batch_size=batch_size,
            callbacks=callbacks,
            verbose=verbose
        )
        
        return history.history
    
    def predict(self, X: np.ndarray) -> np.ndarray:
        """
        Reconstruye secuencias de entrada
        """
        return self.model.predict(X, verbose=0)
    
    def compute_reconstruction_error(self, X: np.ndarray) -> np.ndarray:
        """
        Calcula error de reconstrucción (MSE por muestra)
        """
        reconstructed = self.predict(X)
        mse = np.mean(np.square(X - reconstructed), axis=(1, 2))
        return mse
    
    def save(self, filepath: str):
        """Guarda el modelo entrenado"""
        import json
        import os
        
        # Guardar solo los pesos (más estable) - USAR .weights.h5
        weights_path = filepath.replace('.h5', '.weights.h5')
        self.model.save_weights(weights_path)
        
        # Guardar configuración de la arquitectura
        config_path = filepath.replace('.h5', '_config.json')
        config = {
            'input_shape': self.input_shape,
            'encoder_layers': self.encoder_layers,
            'decoder_layers': self.decoder_layers,
            'dropout': self.dropout
        }
        with open(config_path, 'w') as f:
            json.dump(config, f)
        
        print(f"Modelo guardado en {weights_path} y {config_path}")
    
    def load(self, filepath: str):
        """Carga modelo previamente entrenado"""
        import json
        
        # Cargar configuración
        config_path = filepath.replace('.h5', '_config.json')
        with open(config_path, 'r') as f:
            config = json.load(f)
        
        # Reconstruir arquitectura
        self.input_shape = tuple(config['input_shape'])
        self.encoder_layers = config['encoder_layers']
        self.decoder_layers = config['decoder_layers']
        self.dropout = config['dropout']
        
        # Construir modelo
        self._build_model()
        
        # Cargar pesos - USAR .weights.h5
        weights_path = filepath.replace('.h5', '.weights.h5')
        self.model.load_weights(weights_path)
        
        print(f"Modelo cargado desde {weights_path}")