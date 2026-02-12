#!/usr/bin/env python3
"""
Real-time Anomaly Detection Inference Service

This script runs a continuous anomaly detection service that:
    1. Fetches current metrics from Prometheus (or generates synthetic data)
    2. Preprocesses the data using the trained scaler
    3. Runs inference through the LSTM Autoencoder
    4. Compares reconstruction error against the trained threshold
    5. Sends alerts via Opsgenie when anomalies are detected
    6. Generates Grafana dashboard links for investigation

Prerequisites:
    - Trained model files in models/ directory:
        - lstm_autoencoder.weights.h5
        - lstm_autoencoder_config.json
        - preprocessor.joblib
        - anomaly_threshold.npy
    
Configuration:
    - config/data.yaml: Prometheus connection and data settings
    - config/alerting.yaml: Alert thresholds and Opsgenie settings
    - config/windowing.yaml: Sliding window configuration

Usage:
    python scripts/inference.py
    
    # Or via Docker:
    docker-compose up anomaly-detection

Author: Ing. Christopher Charaf
"""

import os
import sys
import time
import signal
import uuid
from datetime import datetime, timedelta

# Add src directory to Python path for imports
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
    Main service for real-time anomaly detection in TV-over-IP metrics.
    
    This service runs a continuous detection loop that:
        - Fetches current metrics from Prometheus
        - Runs the LSTM autoencoder for reconstruction
        - Detects anomalies based on reconstruction error
        - Sends alerts when anomalies exceed threshold
        - Rate-limits alerts to prevent alert fatigue
    
    Attributes:
        prometheus_client: Client for fetching metrics from Prometheus
        preprocessor: Data preprocessor with trained scaler
        windower: Sliding window generator for time series
        model: Trained LSTM Autoencoder model
        detector: Anomaly detector with threshold logic
        opsgenie_client: Client for sending alerts to Opsgenie
        grafana_links: Generator for Grafana dashboard links
        min_alert_interval: Minimum seconds between alerts (rate limiting)
        inference_minutes: Minutes of data to fetch for each detection cycle
    """
    
    def __init__(self):
        """Initialize the anomaly detection service."""
        self.logger = setup_logger()
        self.config = Config()
        self.running = False
        
        # Component references (initialized in _initialize_components)
        self.prometheus_client = None
        self.preprocessor = None
        self.windower = None
        self.model = None
        self.detector = None
        self.opsgenie_client = None
        self.grafana_links = None
        
        # Alert rate limiting
        self.last_alert_time = None
        self.min_alert_interval = None  # Loaded from config
        self.inference_minutes = None   # Loaded from config
        
        # Anomaly deduplication state
        self.current_anomaly_id = None           # UUID of ongoing anomaly
        self.anomaly_start_time = None           # When anomaly first detected
        self.anomaly_initial_error = None        # Initial reconstruction error
        self.anomaly_peak_error = None           # Peak reconstruction error
        self.last_heartbeat_log_time = None      # Last heartbeat log time
        self.last_escalation_time = None         # Last escalation alert time
        
        # Deduplication config (loaded from YAML)
        self.dedup_enabled = None
        self.min_confidence = None               # Minimum confidence to alert
        self.severity_tolerance = None           # ±20% by default
        self.heartbeat_interval = None           # 180 seconds
        self.escalation_threshold = None         # 30 minutes
        self.escalation_interval = None          # 15 minutes
        self.send_resolved = None
        
        self._initialize_components()
    
    def _initialize_components(self):
        """Inicializa todos los componentes del sistema"""
        self.logger.info("Initializing anomaly detection service...")
        
        try:
            # Read config values
            self.min_alert_interval = self.config.get('alerting.rate_limiting.min_interval_seconds', 300)
            self.inference_minutes = self.config.get('data.features.collection.inference_minutes', 30)
            
            # Metric queries and sampling interval from config
            self.metric_queries = self.config.get('data.metrics.queries', None)
            self.sampling_interval = self.config.get('data.features.collection.sampling_interval', '30s')
            
            # Alert deduplication config
            self.dedup_enabled = self.config.get('alerting.rate_limiting.enable_deduplication', True)
            self.min_confidence = self.config.get('alerting.rate_limiting.min_confidence', 0.10)
            self.severity_tolerance = self.config.get('alerting.rate_limiting.severity_tolerance', 0.2)
            self.heartbeat_interval = self.config.get('alerting.rate_limiting.heartbeat_interval_seconds', 180)
            self.escalation_threshold = self.config.get('alerting.rate_limiting.escalation_threshold_minutes', 30)
            self.escalation_interval = self.config.get('alerting.rate_limiting.escalation_interval_minutes', 15)
            self.send_resolved = self.config.get('alerting.rate_limiting.send_resolved_notification', True)
            
            # Cliente Prometheus
            prometheus_url = self.config.get('data.prometheus.url')
            prometheus_token = self.config.get('data.prometheus.token')
            prometheus_timeout = self.config.get('data.prometheus.timeout_seconds', 30)
            
            if prometheus_url:
                self.prometheus_client = PrometheusClient(
                    prometheus_url, 
                    token=prometheus_token,
                    timeout=prometheus_timeout
                )
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
                opsgenie_base_url = self.config.get('alerting.opsgenie.base_url', 'https://api.opsgenie.com')
                opsgenie_timeout = self.config.get('alerting.opsgenie.timeout_seconds', 10)
                opsgenie_priority_thresholds = self.config.get('alerting.opsgenie.priority_thresholds', None)
                self.opsgenie_client = OpsgenieClient(
                    opsgenie_key,
                    base_url=opsgenie_base_url,
                    timeout=opsgenie_timeout,
                    priority_thresholds=opsgenie_priority_thresholds
                )
                self.logger.info("Opsgenie client initialized")
            else:
                self.logger.warning("Opsgenie not configured - alerts will be logged only")
            
            # Generador enlaces Grafana (opcional)  
            grafana_url = self.config.get('alerting.grafana.base_url')
            grafana_dashboard_uid = self.config.get('alerting.grafana.dashboard_uid')
            if grafana_url:
                self.grafana_links = GrafanaLinkGenerator(grafana_url, dashboard_uid=grafana_dashboard_uid)
                self.logger.info("Grafana link generator initialized")
            
            self.logger.info("=== Service initialization completed ===")
            
        except Exception as e:
            self.logger.error(f"Failed to initialize service: {e}")
            raise
    
    def _get_current_data(self) -> pd.DataFrame:
        """Obtiene datos actuales"""
        if self.prometheus_client:
            try:
                # Convert inference_minutes to hours
                hours_back = self.inference_minutes / 60.0
                df = self.prometheus_client.get_tv_metrics(hours_back=hours_back, queries=self.metric_queries, step=self.sampling_interval)
                if not df.empty:
                    return df
            except Exception as e:
                self.logger.error(f"Error fetching from Prometheus: {e}")
        
        return self._generate_current_synthetic_data()
    
    def _generate_current_synthetic_data(self) -> pd.DataFrame:
        """Genera datos sintéticos para el momento actual"""
        current_time = datetime.now()
        timestamps = pd.date_range(
            start=current_time - timedelta(minutes=self.inference_minutes),
            end=current_time,
            freq='30s'
        )
        
        np.random.seed(int(current_time.timestamp()) % 1000)
        n_points = len(timestamps)
        
        # Daily pattern matching mock service and training generator
        # Peak at hour 14 (2 PM), trough at hour 2 (2 AM)
        hours = np.array([ts.hour for ts in timestamps])
        base_pattern = 0.5 + 0.4 * np.sin(2 * np.pi * (hours - 8) / 24)
        
        # Occasionally inject anomalies for testing
        anomaly_multiplier = 1.0
        if np.random.random() < 0.05:
            anomaly_multiplier = np.random.uniform(2.0, 5.0)
            self.logger.info(f"Injecting synthetic anomaly with multiplier {anomaly_multiplier:.2f}")
        
        # Verified formulas matching real Prometheus data (same as training generator)
        # Memory: noisy constant, no daily cycle
        base_memory = np.random.uniform(500_000_000, 1_500_000_000)
        
        data = {
            'timestamp': timestamps,
            'request_rate': (125 * base_pattern) * anomaly_multiplier + np.random.normal(0, 3, n_points),
            'latency_p95': (0.22 * base_pattern + 0.215) * anomaly_multiplier + np.random.normal(0, 0.015, n_points),
            'memory_usage': (base_memory) * anomaly_multiplier + np.random.normal(0, base_memory * 0.03, n_points),
            'error_rate': (2.5 * base_pattern) * anomaly_multiplier + np.random.normal(0, 0.05, n_points),
            'cpu_usage': 0.125 * base_pattern + np.random.normal(0, 0.005, n_points)
        }
        
        for col in ['request_rate', 'latency_p95', 'error_rate', 'memory_usage', 'cpu_usage']:
            data[col] = np.maximum(data[col], 0)
        
        return pd.DataFrame(data)
    
    def _should_send_alert(self) -> bool:
        """Verifica si se debe enviar alerta"""
        if self.last_alert_time is None:
            return True
        
        time_since_last = (datetime.now() - self.last_alert_time).total_seconds()
        return time_since_last >= self.min_alert_interval
    
    def _is_same_anomaly(self, current_error: float) -> bool:
        """Check if current anomaly is the same as the ongoing one.
        
        Logic:
        - If error is DECREASING (resolving), always treat as same anomaly.
        - If error is INCREASING beyond tolerance, treat as new (worse) anomaly.
        This prevents cascading "severity changed" alerts during wind-down.
        """
        if self.anomaly_initial_error is None:
            return False
        
        # Decreasing or equal error = same anomaly (resolving)
        if current_error <= self.anomaly_initial_error:
            return True
        
        # Increasing error - check if it exceeded the tolerance
        tolerance = self.severity_tolerance
        upper_bound = self.anomaly_initial_error * (1 + tolerance)
        
        return current_error <= upper_bound
    
    def _should_send_heartbeat(self) -> bool:
        """Check if it's time for heartbeat log"""
        if not self.dedup_enabled or self.last_heartbeat_log_time is None:
            return True  # First heartbeat
        
        elapsed = (datetime.now() - self.last_heartbeat_log_time).total_seconds()
        return elapsed >= self.heartbeat_interval
    
    def _should_escalate(self) -> bool:
        """Check if anomaly has lasted long enough to escalate"""
        if self.anomaly_start_time is None:
            return False
        
        duration_minutes = (datetime.now() - self.anomaly_start_time).total_seconds() / 60
        
        # First escalation at threshold
        if duration_minutes >= self.escalation_threshold:
            # Check if we've escalated before
            if self.last_escalation_time is None:
                return True
            
            # Subsequent escalations at interval
            time_since_last = (datetime.now() - self.last_escalation_time).total_seconds() / 60
            return time_since_last >= self.escalation_interval
        
        return False
    
    def _send_heartbeat_log(self, detection_result: dict):
        """Log ongoing anomaly status"""
        duration = int((datetime.now() - self.anomaly_start_time).total_seconds())
        duration_str = f"{duration//60}m {duration%60}s"
        
        current_error = detection_result['reconstruction_error']
        initial_error = self.anomaly_initial_error
        peak_error = self.anomaly_peak_error or current_error
        
        self.logger.info(f"⏱️ Anomaly ongoing for {duration_str}")
        self.logger.info(f"   Current error: {current_error:.4f} (initial: {initial_error:.4f}, peak: {peak_error:.4f})")
        self.logger.info(f"   Anomaly ID: {self.current_anomaly_id}")
        
        self.last_heartbeat_log_time = datetime.now()
    
    def _send_escalation_alert(self, detection_result: dict):
        """Send escalation alert for long-running anomaly"""
        duration = int((datetime.now() - self.anomaly_start_time).total_seconds() / 60)
        
        self.logger.warning(f"⚠️ ESCALATION: Anomaly ongoing for {duration} minutes")
        self.logger.warning(f"   Anomaly ID: {self.current_anomaly_id}")
        self.logger.warning(f"   Current error: {detection_result['reconstruction_error']:.4f}")
        self.logger.warning(f"   Initial error: {self.anomaly_initial_error:.4f}")
        
        # Send to Opsgenie if configured
        if self.opsgenie_client:
            # Modify detection result to indicate escalation
            escalation_result = detection_result.copy()
            escalation_result['is_escalation'] = True
            escalation_result['duration_minutes'] = duration
            escalation_result['initial_error'] = self.anomaly_initial_error
            
            grafana_link = None
            if self.grafana_links:
                grafana_link = self.grafana_links.generate_anomaly_link(detection_result['timestamp'])
            
            result = self.opsgenie_client.create_alert(escalation_result, grafana_link)
            if result['status'] == 'success':
                self.logger.info(f"Escalation alert sent to Opsgenie: {result['alert_id']}")
        
        self.last_escalation_time = datetime.now()
    
    def _send_resolved_notification(self):
        """Send notification when anomaly resolves"""
        if not self.send_resolved or self.anomaly_start_time is None:
            return
        
        duration = int((datetime.now() - self.anomaly_start_time).total_seconds())
        duration_str = f"{duration//60}m {duration%60}s"
        
        self.logger.warning(f"✅ RESOLVED: Anomaly cleared after {duration_str}")
        self.logger.warning(f"   Anomaly ID: {self.current_anomaly_id}")
        self.logger.warning(f"   Initial error: {self.anomaly_initial_error:.4f}, Peak: {self.anomaly_peak_error:.4f}")
        
        # Send to Opsgenie if configured
        if self.opsgenie_client:
            # Create resolved alert payload
            resolved_payload = {
                'is_anomaly': False,
                'is_resolved': True,
                'anomaly_id': self.current_anomaly_id,
                'duration_seconds': duration,
                'initial_error': self.anomaly_initial_error,
                'timestamp': datetime.now().isoformat()
            }
            
            result = self.opsgenie_client.create_resolved_alert(resolved_payload)
            if result['status'] == 'success':
                self.logger.info(f"Resolved notification sent to Opsgenie")
    
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
            
            self.logger.debug(f"Retrieved {len(current_data)} data points")
            
            detection_result = self.detector.detect(current_data)
            is_anomaly = detection_result.get('is_anomaly', False)
            reconstruction_error = detection_result['reconstruction_error']
            confidence = detection_result.get('confidence', 0)
            
            if not self.dedup_enabled:
                # Legacy behavior - no deduplication
                if is_anomaly:
                    self._log_anomaly_metrics(current_data)
                    self._send_alert(detection_result)
                else:
                    self.logger.debug(f"Normal operation - reconstruction error: {reconstruction_error:.4f}")
            else:
                # Deduplication logic with confidence filtering
                if is_anomaly:
                    # Check confidence threshold first
                    if confidence < self.min_confidence:
                        self.logger.debug(f"Filtered (low confidence) - error: {reconstruction_error:.4f}, confidence: {confidence:.4f} < {self.min_confidence:.2f}")
                        # Treat as normal for deduplication purposes
                        is_anomaly = False
                
                if is_anomaly:
                    # Check if this is a new or ongoing anomaly
                    if self.current_anomaly_id is None:
                        # NEW ANOMALY - first detection
                        self.current_anomaly_id = str(uuid.uuid4())
                        self.anomaly_start_time = datetime.now()
                        self.anomaly_initial_error = reconstruction_error
                        self.anomaly_peak_error = reconstruction_error
                        self.last_heartbeat_log_time = datetime.now()
                        self.last_escalation_time = None
                        
                        # Full alert
                        self.logger.warning("🚨 NEW ANOMALY DETECTED")
                        self._log_anomaly_metrics(current_data)
                        self._send_alert(detection_result)
                        
                    else:
                        # ONGOING ANOMALY - track peak error
                        if reconstruction_error > self.anomaly_peak_error:
                            self.anomaly_peak_error = reconstruction_error
                        
                        if self._should_escalate():
                            self._send_escalation_alert(detection_result)
                        elif self._should_send_heartbeat():
                            self._send_heartbeat_log(detection_result)
                        # else: silent (deduplication working)
                        
                else:
                    # No anomaly detected
                    if self.current_anomaly_id is not None:
                        # Anomaly just resolved
                        self._send_resolved_notification()
                        
                        # Clear state
                        self.current_anomaly_id = None
                        self.anomaly_start_time = None
                        self.anomaly_initial_error = None
                        self.anomaly_peak_error = None
                        self.last_heartbeat_log_time = None
                        self.last_escalation_time = None
                    else:
                        # Normal operation
                        self.logger.debug(f"Normal - error: {reconstruction_error:.4f} (threshold: {detection_result['threshold']:.4f})")
            
        except Exception as e:
            self.logger.error(f"Error in detection cycle: {e}")
            import traceback
            self.logger.error(traceback.format_exc())
    
    def _log_anomaly_metrics(self, data: pd.DataFrame):
        """Log detailed metrics when anomaly is detected"""
        if data.empty:
            return
        
        # Get latest metrics (most recent row)
        latest = data.iloc[-1]
        
        self.logger.warning("📊 Current Metrics:")
        metric_cols = [col for col in data.columns if col != 'timestamp']
        for col in metric_cols:
            value = latest[col]
            # Format based on metric type
            if 'memory' in col:
                value_str = f"{value/1e9:.2f} GB"
            elif 'rate' in col or 'cpu' in col:
                value_str = f"{value:.2f}"
            elif 'latency' in col:
                value_str = f"{value:.3f}s"
            else:
                value_str = f"{value:.2f}"
            self.logger.warning(f"   {col}: {value_str}")
        
        # Show average over the window for comparison
        self.logger.warning("📈 Average (inference window):")
        for col in metric_cols:
            avg = data[col].mean()
            if 'memory' in col:
                avg_str = f"{avg/1e9:.2f} GB"
            elif 'rate' in col or 'cpu' in col:
                avg_str = f"{avg:.2f}"
            elif 'latency' in col:
                avg_str = f"{avg:.3f}s"
            else:
                avg_str = f"{avg:.2f}"
            self.logger.warning(f"   {col}: {avg_str}")
    
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
