"""
LSTM Autoencoder for Time Series Anomaly Detection

This module implements an LSTM-based autoencoder neural network for detecting
anomalies in time series data. The model learns to reconstruct normal patterns,
and anomalies are detected when reconstruction error exceeds a threshold.

Architecture:
    Encoder: Multiple LSTM layers that compress the input sequence
    Latent: Bottleneck representation capturing essential patterns
    Decoder: Multiple LSTM layers that reconstruct the original sequence

The model is trained only on normal data. During inference, high reconstruction
error indicates the input deviates from learned normal patterns (anomaly).
"""

import tensorflow as tf
from tensorflow import keras
from keras import layers
import numpy as np
from typing import List, Tuple


class LSTMAutoencoder:
    """
    LSTM-based Autoencoder for time series anomaly detection.
    
    This model learns to reconstruct normal time series patterns. During inference,
    anomalies are detected by comparing reconstruction error against a threshold
    computed from validation data.
    
    Architecture:
        - Encoder: Stacked LSTM layers with decreasing units (compression)
        - Latent space: Dense representation of the input sequence
        - Decoder: Stacked LSTM layers with increasing units (reconstruction)
        - Output: TimeDistributed Dense layer to match input shape
    
    Attributes:
        input_shape: Tuple of (sequence_length, n_features)
        encoder_layers: List of units for each encoder LSTM layer
        decoder_layers: List of units for each decoder LSTM layer
        dropout: Dropout rate between layers for regularization
        learning_rate: Learning rate for optimizer
        optimizer_name: Name of optimizer ('adam', 'sgd', 'rmsprop')
        model: Compiled Keras model (encoder + decoder)
        encoder: Separate encoder model for extracting latent representations
    
    Example:
        >>> model = LSTMAutoencoder(input_shape=(20, 10))
        >>> history = model.train(X_train, X_val, epochs=50)
        >>> errors = model.compute_reconstruction_error(X_test)
    """
    
    def __init__(self, input_shape: Tuple[int, int], 
                 encoder_layers: List[int] = [64, 32, 16],
                 decoder_layers: List[int] = [16, 32, 64],
                 dropout: float = 0.1,
                 learning_rate: float = 0.001,
                 optimizer: str = 'adam'):
        """
        Initialize the LSTM Autoencoder.
        
        Args:
            input_shape: Tuple of (sequence_length, n_features)
            encoder_layers: List of LSTM units for encoder layers [64, 32, 16]
            decoder_layers: List of LSTM units for decoder layers [16, 32, 64]
            dropout: Dropout rate between layers (0.0 to 1.0)
            learning_rate: Learning rate for optimizer
            optimizer: Optimizer name ('adam', 'sgd', 'rmsprop')
        """
        self.input_shape = input_shape
        self.encoder_layers = encoder_layers
        self.decoder_layers = decoder_layers
        self.dropout = dropout
        self.learning_rate = learning_rate
        self.optimizer_name = optimizer
        self.model = None
        self.encoder = None
        
        self._build_model()
    
    def _build_model(self):
        """
        Build the LSTM autoencoder architecture.
        
        Creates a sequence-to-sequence model with:
            - Stacked LSTM encoder layers (compress input)
            - Latent representation (bottleneck)
            - RepeatVector to expand latent to sequence length
            - Stacked LSTM decoder layers (reconstruct input)
            - TimeDistributed Dense output layer
        """
        # Input layer: (batch_size, sequence_length, n_features)
        inputs = keras.Input(shape=self.input_shape)
        
        # === ENCODER ===
        # Stacked LSTM layers with decreasing units to compress input
        # Use default Keras naming (lstm, lstm_1, ...) for save/load compatibility
        x = inputs
        for units in self.encoder_layers[:-1]:
            x = layers.LSTM(units, return_sequences=True)(x)
            x = layers.Dropout(self.dropout)(x)
        
        # Final encoder layer outputs the latent representation (no sequences)
        latent = layers.LSTM(self.encoder_layers[-1], return_sequences=False)(x)
        
        # === DECODER ===
        # Repeat latent vector to match original sequence length
        x = layers.RepeatVector(self.input_shape[0])(latent)
        
        # Stacked LSTM layers with increasing units to reconstruct input
        # All decoder LSTM layers must have return_sequences=True
        for units in self.decoder_layers:
            x = layers.LSTM(units, return_sequences=True)(x)
            x = layers.Dropout(self.dropout)(x)
        
        # Output layer: Apply Dense to each timestep to match input features
        outputs = layers.TimeDistributed(
            layers.Dense(self.input_shape[1], activation='linear')
        )(x)
        
        # === COMPILE MODEL ===
        self.model = keras.Model(inputs=inputs, outputs=outputs, name='lstm_autoencoder')
        
        # Create optimizer with configurable learning rate
        if self.optimizer_name.lower() == 'adam':
            optimizer = keras.optimizers.Adam(learning_rate=self.learning_rate)
        elif self.optimizer_name.lower() == 'sgd':
            optimizer = keras.optimizers.SGD(learning_rate=self.learning_rate)
        elif self.optimizer_name.lower() == 'rmsprop':
            optimizer = keras.optimizers.RMSprop(learning_rate=self.learning_rate)
        else:
            optimizer = keras.optimizers.Adam(learning_rate=self.learning_rate)
        
        # Use MSE loss for reconstruction (autoencoder objective)
        self.model.compile(optimizer=optimizer, loss='mse', metrics=['mae'])
        
        # Create standalone encoder model for extracting latent representations
        self.encoder = keras.Model(inputs=inputs, outputs=latent, name='encoder')
    
    def train(self, X_train: np.ndarray, X_val: np.ndarray = None, 
              epochs: int = 50, batch_size: int = 32, verbose: int = 1,
              early_stopping: bool = True, patience: int = 10) -> dict:
        """
        Train the autoencoder on normal data.
        
        The model learns to reconstruct normal patterns. During training,
        the model minimizes the Mean Squared Error between input and output.
        
        Callbacks:
            - EarlyStopping: Stops training when validation loss stops improving
            - ReduceLROnPlateau: Reduces learning rate when loss plateaus
        
        Args:
            X_train: Training data of shape (n_samples, sequence_length, n_features)
            X_val: Validation data (optional) for early stopping and monitoring
            epochs: Maximum number of training epochs
            batch_size: Number of samples per gradient update
            verbose: Verbosity mode (0=silent, 1=progress bar, 2=one line per epoch)
            early_stopping: Whether to stop training early when validation loss plateaus
            patience: Number of epochs with no improvement before stopping
        
        Returns:
            dict: Training history with 'loss', 'val_loss', 'mae', 'val_mae' keys
        """
        callbacks = []
        
        if early_stopping:
            callbacks.append(
                keras.callbacks.EarlyStopping(
                    monitor='val_loss' if X_val is not None else 'loss',
                    patience=patience,
                    restore_best_weights=True
                )
            )
        
        callbacks.append(
            keras.callbacks.ReduceLROnPlateau(
                monitor='val_loss' if X_val is not None else 'loss',
                factor=0.5,
                patience=max(3, patience // 2),
                min_lr=1e-7
            )
        )
        
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
        Reconstruct input sequences.
        
        Passes the input through the encoder-decoder to generate reconstructions.
        
        Args:
            X: Input data of shape (n_samples, sequence_length, n_features)
        
        Returns:
            np.ndarray: Reconstructed sequences of same shape as input
        """
        return self.model.predict(X, verbose=0)
    
    def compute_reconstruction_error(self, X: np.ndarray) -> np.ndarray:
        """
        Compute reconstruction error (MSE) for each sample.
        
        The reconstruction error measures how well the model can reconstruct
        each input sequence. Higher error indicates the input deviates from
        normal patterns (potential anomaly).
        
        Args:
            X: Input data of shape (n_samples, sequence_length, n_features)
        
        Returns:
            np.ndarray: MSE for each sample, shape (n_samples,)
        """
        reconstructed = self.predict(X)
        # Compute MSE across time steps and features for each sample
        mse = np.mean(np.square(X - reconstructed), axis=(1, 2))
        return mse
    
    def save(self, filepath: str):
        """
        Save the trained model to disk.
        
        Saves model weights and architecture configuration separately for
        better stability and portability across TensorFlow versions.
        
        Files created:
            - Weights: filepath with '.h5' replaced by '.weights.h5' (e.g. models/lstm_autoencoder.weights.h5)
            - Config: filepath with '.h5' replaced by '_config.json' (e.g. models/lstm_autoencoder_config.json)
        
        Args:
            filepath: Base path for saving (e.g., 'models/lstm_autoencoder.h5')
        """
        import json
        
        # Save weights separately (more stable than full model save)
        weights_path = filepath.replace('.h5', '.weights.h5')
        self.model.save_weights(weights_path)
        
        # Save architecture configuration as JSON
        config_path = filepath.replace('.h5', '_config.json')
        config = {
            'input_shape': self.input_shape,
            'encoder_layers': self.encoder_layers,
            'decoder_layers': self.decoder_layers,
            'dropout': self.dropout,
            'learning_rate': self.learning_rate,
            'optimizer': self.optimizer_name
        }
        with open(config_path, 'w') as f:
            json.dump(config, f, indent=2)
        
        print(f"Model saved to {weights_path} and {config_path}")
    
    def load(self, filepath: str):
        """
        Load a previously saved model from disk.
        
        Rebuilds the model architecture from the config file and loads
        the trained weights.
        
        Args:
            filepath: Base path for loading (e.g., 'models/lstm_autoencoder.h5')

        Expects:
            - Weights file: filepath with '.h5' replaced by '.weights.h5'
            - Config file: filepath with '.h5' replaced by '_config.json'
        """
        import json
        
        # Load architecture configuration
        config_path = filepath.replace('.h5', '_config.json')
        with open(config_path, 'r') as f:
            config = json.load(f)
        
        # Restore architecture parameters
        self.input_shape = tuple(config['input_shape'])
        self.encoder_layers = config['encoder_layers']
        self.decoder_layers = config['decoder_layers']
        self.dropout = config['dropout']
        self.learning_rate = config.get('learning_rate', 0.001)
        self.optimizer_name = config.get('optimizer', 'adam')
        
        # Rebuild model architecture
        self._build_model()
        
        # Load trained weights
        weights_path = filepath.replace('.h5', '.weights.h5')
        self.model.load_weights(weights_path)
        
        print(f"Model loaded from {weights_path}")