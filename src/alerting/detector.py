import pandas as pd
from typing import Dict
from datetime import datetime

class AnomalyDetector:
    """
    Detector de anomalías usando error de reconstrucción
    """
    
    def __init__(self, threshold: float, model, preprocessor, windower):
        self.threshold = threshold
        self.model = model
        self.preprocessor = preprocessor
        self.windower = windower
        self.detection_history = []
    
    def detect(self, data: pd.DataFrame) -> Dict:
        """
        Detecta anomalías en datos en tiempo real
        """
        try:
            # Preprocesar datos
            processed_data = self.preprocessor.transform(data)
            
            # Crear ventana
            window = self.windower.create_single_window(processed_data)
            
            # Calcular error de reconstrucción
            reconstruction_error = self.model.compute_reconstruction_error(window)[0]
            
            # Determinar si es anomalía
            is_anomaly = reconstruction_error > self.threshold
            
            # Obtener reconstrucción para comparación
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
            
            # Guardar en historial
            self.detection_history.append(detection_result)
            
            # Mantener solo últimos 1000 registros
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
