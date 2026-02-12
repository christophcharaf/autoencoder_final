import pandas as pd
from typing import Dict
from datetime import datetime

class AnomalyDetector:
    """
    Anomaly detector using reconstruction error threshold.

    Preprocesses input data, creates a sliding window, runs the LSTM autoencoder,
    and flags anomalies when reconstruction error exceeds the configured threshold.
    """

    def __init__(self, threshold: float, model, preprocessor, windower):
        self.threshold = threshold
        self.model = model
        self.preprocessor = preprocessor
        self.windower = windower
        self.detection_history = []
    
    def detect(self, data: pd.DataFrame) -> Dict:
        """
        Detect anomalies in real-time metric data.

        Args:
            data: Raw DataFrame with TV-over-IP metrics.

        Returns:
            Dict with keys: is_anomaly, reconstruction_error, threshold,
            confidence, original_values, reconstructed_values, feature_columns.
        """
        try:
            processed_data = self.preprocessor.transform(data)
            window = self.windower.create_single_window(processed_data)
            reconstruction_error = self.model.compute_reconstruction_error(window)[0]
            is_anomaly = reconstruction_error > self.threshold
            reconstructed = self.model.predict(window)[0]
            original = window[0]
            
            detection_result = {
                'timestamp': datetime.now().isoformat(),
                'is_anomaly': bool(is_anomaly),
                'reconstruction_error': float(reconstruction_error),
                'threshold': float(self.threshold),
                'confidence': float((reconstruction_error - self.threshold) / self.threshold) if is_anomaly else 0.0,
                'original_values': original.tolist(),
                'reconstructed_values': reconstructed.tolist(),
                'feature_columns': self.preprocessor.feature_columns
            }
            
            self.detection_history.append(detection_result)
            if len(self.detection_history) > 1000:
                self.detection_history = self.detection_history[-1000:]
            
            return detection_result
            
        except Exception as e:
            return {
                'timestamp': datetime.now().isoformat(),
                'is_anomaly': False,
                'error': str(e),
                'reconstruction_error': 0.0,
                'threshold': float(self.threshold)
            }
