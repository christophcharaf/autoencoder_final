#!/usr/bin/env python3

"""
Script de inferencia para detección de anomalías en tiempo real
"""

import os
import sys
import time
import signal
from datetime import datetime, timedelta

# Agregar src al path
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'src'))

from utils.config import Config
from utils.logging import setup_logger
from data.prometheus_client import PrometheusClient
from data.preprocessor import DataPreprocessor
from data.windowing import WindowGenerator
from models.lstm_autoencoder import LSTMAutoencoder
from alerting.detector import AnomalyDetector
from alerting.opsgenie_client import OpsgenieClient
from alerting.grafana_links import GrafanaLinkGenerator

import numpy as np
import pandas as pd

class AnomalyDetectionService:
    """
    Servicio principal de detección de anomalías
    """
    
    def __init__(self):
        self.logger = setup_logger()
        self.config = Config()
        self.running = False
        
        self.prometheus_client = None
        self.preprocessor = None
        self.windower = None
        self.model = None
        self.detector = None
        self.opsgenie_client = None
        self.grafana_links = None
        
        self.last_alert_time = None
        self.min_alert_interval = 300  # 5 minutos
        
        self._initialize_components()
    
    def _initialize_components(self):
        """Inicializa todos los componentes del sistema"""
        self.logger.info("Initializing anomaly detection service...")
        
        try:
            # Cliente Prometheus
            prometheus_url = self.config.get('data.prometheus_url')
            if prometheus_url:
                self.prometheus_client = PrometheusClient(prometheus_url)
                self.logger.info(f"Prometheus client initialized: {prometheus_url}")
            else:
                self.logger.warning("No Prometheus URL configured - using synthetic data")
            
            # Cargar preprocessor
            if os.path.exists('models/preprocessor.joblib'):
                self.preprocessor = DataPreprocessor()
                self.preprocessor.load_scaler('models/preprocessor.joblib')
                self.logger.info("Preprocessor loaded")
            else:
                raise FileNotFoundError("Preprocessor not found. Please train model first.")
            
            # Configurar windower
            window_size = self.config.get('windowing.window_size', 20)
            self.windower = WindowGenerator(window_size=window_size)
            
            # Cargar modelo
            if os.path.exists('models/lstm_autoencoder.weights.h5') and os.path.exists('models/lstm_autoencoder_config.json'):
                n_features = len(self.preprocessor.feature_columns) if self.preprocessor.feature_columns else 5
                input_shape = (window_size, n_features)
                
                self.model = LSTMAutoencoder(input_shape=input_shape)
                self.model.load('models/lstm_autoencoder.h5')
                self.logger.info("LSTM Autoencoder model loaded")
            else:
                raise FileNotFoundError("Model not found. Please train model first.")
            
            # Cargar threshold
            if os.path.exists('models/anomaly_threshold.npy'):
                threshold = np.load('models/anomaly_threshold.npy')
                self.detector = AnomalyDetector(
                    threshold=threshold,
                    model=self.model,
                    preprocessor=self.preprocessor,
                    windower=self.windower
                )
                self.logger.info(f"Anomaly detector initialized with threshold: {threshold:.4f}")
            else:
                raise FileNotFoundError("Threshold not found. Please train model first.")
            
            # Cliente Opsgenie (opcional)
            opsgenie_key = self.config.get('alerting.opsgenie.api_key')
            if opsgenie_key and opsgenie_key != "your_api_key_here":
                self.opsgenie_client = OpsgenieClient(opsgenie_key)
                self.logger.info("Opsgenie client initialized")
            else:
                self.logger.warning("Opsgenie not configured - alerts will be logged only")
            
            # Generador enlaces Grafana (opcional)  
            grafana_url = self.config.get('alerting.grafana.base_url')
            if grafana_url:
                self.grafana_links = GrafanaLinkGenerator(grafana_url)
                self.logger.info("Grafana link generator initialized")
            
            self.logger.info("=== Service initialization completed ===")
            
        except Exception as e:
            self.logger.error(f"Failed to initialize service: {e}")
            raise
    
    def _get_current_data(self) -> pd.DataFrame:
        """Obtiene datos actuales"""
        if self.prometheus_client:
            try:
                df = self.prometheus_client.get_tv_metrics(hours_back=0.5)
                if not df.empty:
                    return df
            except Exception as e:
                self.logger.error(f"Error fetching from Prometheus: {e}")
        
        return self._generate_current_synthetic_data()
    
    def _generate_current_synthetic_data(self) -> pd.DataFrame:
        """Genera datos sintéticos para el momento actual"""
        current_time = datetime.now()
        timestamps = pd.date_range(
            start=current_time - timedelta(minutes=30),
            end=current_time,
            freq='30s'
        )
        
        np.random.seed(int(current_time.timestamp()) % 1000)
        n_points = len(timestamps)
        
        hours = np.array([ts.hour for ts in timestamps])
        base_pattern = 0.5 + 0.3 * np.sin(2 * np.pi * hours / 24)
        
        # Ocasionalmente introducir anomalías para testing
        anomaly_multiplier = 1.0
        if np.random.random() < 0.05:
            anomaly_multiplier = np.random.uniform(2.0, 5.0)
            self.logger.info(f"Injecting synthetic anomaly with multiplier {anomaly_multiplier:.2f}")
        
        data = {
            'timestamp': timestamps,
            'request_rate': base_pattern * 1000 * anomaly_multiplier + np.random.normal(0, 50, n_points),
            'latency_p95': base_pattern * 200 * anomaly_multiplier + 100 + np.random.normal(0, 20, n_points),
            'memory_usage': np.clip(base_pattern * 0.7 + 0.3 + np.random.normal(0, 0.05, n_points), 0, 1),
            'error_rate': np.random.exponential(0.01 * anomaly_multiplier, n_points),
            'cpu_usage': np.clip(base_pattern * 0.8 + 0.2 + np.random.normal(0, 0.1, n_points), 0, 1)
        }
        
        for col in ['request_rate', 'latency_p95', 'error_rate']:
            data[col] = np.maximum(data[col], 0)
        
        return pd.DataFrame(data)
    
    def _should_send_alert(self) -> bool:
        """Verifica si se debe enviar alerta"""
        if self.last_alert_time is None:
            return True
        
        time_since_last = (datetime.now() - self.last_alert_time).total_seconds()
        return time_since_last >= self.min_alert_interval
    
    def _send_alert(self, detection_result: dict):
        """Envía alerta por los canales configurados"""
        try:
            # Generar enlace Grafana
            grafana_link = None
            if self.grafana_links:
                grafana_link = self.grafana_links.generate_anomaly_link(
                    detection_result['timestamp']
                )
            
            # Log local
            self.logger.warning(f"🚨 ANOMALY DETECTED:")
            self.logger.warning(f"   Reconstruction error: {detection_result['reconstruction_error']:.4f}")
            self.logger.warning(f"   Threshold: {detection_result['threshold']:.4f}")
            self.logger.warning(f"   Confidence: {detection_result.get('confidence', 0):.2f}")
            if grafana_link:
                self.logger.warning(f"   Grafana: {grafana_link}")
            
            # Opsgenie
            if self.opsgenie_client and self._should_send_alert():
                result = self.opsgenie_client.create_alert(detection_result, grafana_link)
                if result['status'] == 'success':
                    self.logger.info(f"Alert sent to Opsgenie: {result['alert_id']}")
                    self.last_alert_time = datetime.now()
                else:
                    self.logger.error(f"Failed to send Opsgenie alert: {result}")
            
        except Exception as e:
            self.logger.error(f"Error sending alert: {e}")
    
    def run_detection_cycle(self):
        """Ejecuta un ciclo de detección"""
        try:
            current_data = self._get_current_data()
            
            if current_data.empty:
                self.logger.warning("No data available for detection")
                return
            
            detection_result = self.detector.detect(current_data)
            
            if detection_result.get('is_anomaly', False):
                self._send_alert(detection_result)
            else:
                self.logger.debug(f"Normal operation - reconstruction error: {detection_result['reconstruction_error']:.4f}")
            
        except Exception as e:
            self.logger.error(f"Error in detection cycle: {e}")
    
    def start(self):
        """Inicia el servicio de detección"""
        self.logger.info("🚀 Starting anomaly detection service...")
        self.running = True
        
        def signal_handler(signum, frame):
            self.logger.info(f"Received signal {signum}, shutting down...")
            self.stop()
        
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
        
        cycle_interval = 30  # 30 segundos
        
        while self.running:
            cycle_start = time.time()
            
            self.run_detection_cycle()
            
            cycle_duration = time.time() - cycle_start
            sleep_time = max(0, cycle_interval - cycle_duration)
            
            if sleep_time > 0:
                time.sleep(sleep_time)
        
        self.logger.info("Anomaly detection service stopped")
    
    def stop(self):
        """Detiene el servicio"""
        self.running = False

def main():
    """Función principal"""
    try:
        service = AnomalyDetectionService()
        
        print("=== Starting monitoring ===")
        print("Press Ctrl+C to stop...")
        
        service.start()
        
    except KeyboardInterrupt:
        print("\nShutdown requested by user")
    except Exception as e:
        print(f"Service failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
