#!/usr/bin/env python3

"""
Script para generar estructura completa del repositorio GitHub
Sistema de Detección de Anomalías TV-over-IP
"""

import os
from pathlib import Path
import subprocess
import sys

def create_file_structure():
    """Crea la estructura completa de archivos del proyecto"""
    
    files_content = {
        # =============================================================================
        # Root files
        # =============================================================================
        
        "README.md": '''# Sistema de Detección de Anomalías TV-over-IP

## Descripción

Sistema de detección de anomalías en tiempo real para servicios de TV-over-IP utilizando un autoencoder LSTM. Detecta patrones inusuales en métricas del servicio y envía alertas automáticas.

## Características del MVP

✅ **Recolección de métricas** desde Prometheus API  
✅ **Preprocesamiento** con feature engineering temporal  
✅ **Modelo LSTM Autoencoder** para detección de anomalías  
✅ **Alertas automáticas** via Opsgenie  
✅ **Enlaces contextuales** a dashboards Grafana  
✅ **Containerización** con Docker  
✅ **Configuración flexible** via YAML  

## Instalación Rápida

```bash
# Clonar repositorio
git clone https://github.com/tu-usuario/tv-anomaly-detection.git
cd tv-anomaly-detection

# Setup automático
python scripts/setup.py

# Configurar variables
cp .env.example .env
# Editar .env con tus configuraciones

# Entrenar modelo
python scripts/train.py

# Iniciar detección
python scripts/inference.py
```

## Estructura del Proyecto

```
anomaly-detection/
├── src/                          # Código fuente
│   ├── data/                     # Módulos de datos
│   ├── models/                   # Modelos ML
│   ├── alerting/                 # Sistema de alertas
│   └── utils/                    # Utilidades
├── config/                       # Archivos configuración
├── scripts/                      # Scripts principales
├── models/                       # Modelos entrenados
├── tests/                        # Tests
├── docs/                         # Documentación
└── infrastructure/               # Deployment
```

## Uso

### Entrenamiento
```bash
python scripts/train.py
```

### Detección en Tiempo Real
```bash
python scripts/inference.py
```

### Deployment con Docker
```bash
./scripts/deploy.sh development
```

## Configuración

El sistema usa archivos YAML para configuración:

- `config/model.yaml` - Parámetros del modelo LSTM
- `config/windowing.yaml` - Configuración de ventanas deslizantes  
- `config/alerting.yaml` - Sistema de alertas
- `config/data.yaml` - Fuentes de datos

## Documentación

Ver [documentación completa](docs/) para:

- [Guía de instalación](docs/installation.md)
- [Configuración avanzada](docs/configuration.md)
- [Troubleshooting](docs/troubleshooting.md)

## Contribución

1. Fork el proyecto
2. Crear feature branch (`git checkout -b feature/nueva-funcionalidad`)
3. Commit cambios (`git commit -am 'Agregar nueva funcionalidad'`)
4. Push branch (`git push origin feature/nueva-funcionalidad`)
5. Crear Pull Request

## Licencia

Este proyecto es parte del Trabajo Final de la Especialización en Inteligencia Artificial.

**Autor**: Ing. Christopher Charaf  
**Cliente**: Kaltura Inc.
''',

        "requirements.txt": '''numpy==1.21.6
pandas==1.5.3
tensorflow==2.13.0
scikit-learn==1.3.0
requests==2.31.0
pyyaml==6.0
python-dotenv==1.0.0
prometheus-api-client==0.5.3
joblib==1.3.0

# Development dependencies
pytest==7.4.0
flake8==6.0.0
black==23.0.0
memory-profiler==0.60.0
''',

        ".env.example": '''# Configuración de Prometheus
PROMETHEUS_URL=http://localhost:9090
PROMETHEUS_TOKEN=

# Configuración de Opsgenie
OPSGENIE_API_KEY=your_api_key_here

# Configuración de Grafana  
GRAFANA_URL=http://localhost:3000

# Configuración de entorno
ENVIRONMENT=development
PYTHONPATH=/app/src

# Configuración de logging
LOG_LEVEL=INFO

# Configuración AWS (opcional)
AWS_REGION=us-east-1
AWS_ACCESS_KEY_ID=
AWS_SECRET_ACCESS_KEY=
''',

        ".gitignore": '''# Python
__pycache__/
*.py[cod]
*$py.class
*.so
.Python
env/
venv/
ENV/
*.egg-info/
dist/
build/

# Modelos entrenados
models/*.h5
models/*.joblib
models/*.npy
models/*.pkl

# Logs
logs/
*.log

# Configuración local
.env
config/local*.yaml

# IDE
.vscode/
.idea/
*.swp
*.swo

# OS
.DS_Store
Thumbs.db

# Docker
.dockerignore

# Archivos temporales
*.tmp
temp/

# Prometheus data
prometheus_data/

# Grafana data
grafana_data/
''',

        "Dockerfile": '''FROM python:3.8-slim

# Instalar dependencias del sistema
RUN apt-get update && apt-get install -y \\
    gcc \\
    g++ \\
    && rm -rf /var/lib/apt/lists/*

# Crear usuario no-root
RUN useradd --create-home --shell /bin/bash anomaly_user

WORKDIR /app

# Copiar requirements y instalar dependencias Python
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copiar código fuente
COPY src/ ./src/
COPY config/ ./config/
COPY scripts/ ./scripts/

# Crear directorios necesarios
RUN mkdir -p models/ logs/ && \\
    chown -R anomaly_user:anomaly_user /app

# Cambiar a usuario no-root
USER anomaly_user

# Exponer puerto
EXPOSE 8080

# Comando por defecto
CMD ["python", "scripts/inference.py"]
''',

        "docker-compose.yml": '''version: '3.8'

services:
  anomaly-detection:
    build: .
    container_name: tv-anomaly-detector
    restart: unless-stopped
    
    environment:
      - PROMETHEUS_URL=${PROMETHEUS_URL:-http://prometheus:9090}
      - PROMETHEUS_TOKEN=${PROMETHEUS_TOKEN:-}
      - OPSGENIE_API_KEY=${OPSGENIE_API_KEY:-}
      - GRAFANA_URL=${GRAFANA_URL:-http://grafana:3000}
      - PYTHONPATH=/app/src
      
    volumes:
      - ./models:/app/models
      - ./logs:/app/logs
      - ./config:/app/config
      
    networks:
      - monitoring
    
    healthcheck:
      test: ["CMD", "python", "-c", "import sys; sys.exit(0)"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 60s
    
    deploy:
      resources:
        limits:
          cpus: '1.0'
          memory: 2G
        reservations:
          cpus: '0.5'
          memory: 1G

  # Servicios opcionales para desarrollo
  prometheus:
    image: prom/prometheus:latest
    container_name: prometheus
    ports:
      - "9090:9090"
    volumes:
      - ./prometheus.yml:/etc/prometheus/prometheus.yml
    networks:
      - monitoring
    profiles:
      - dev

  grafana:
    image: grafana/grafana:latest
    container_name: grafana
    ports:
      - "3000:3000"
    environment:
      - GF_SECURITY_ADMIN_PASSWORD=admin
    networks:
      - monitoring
    profiles:
      - dev

networks:
  monitoring:
    driver: bridge
''',

        # =============================================================================
        # Config files
        # =============================================================================

        "config/windowing.yaml": '''windowing:
  # Configuración base para MVP
  window_size: 20          # pasos temporales (10 minutos con muestreo de 30s)
  step_size: 30            # segundos por paso
  stride: 20               # sin solapamiento para MVP
  
  # Configuraciones experimentales (para Fase 2)
  experimental:
    enable_overlap: false  # deshabilitado en MVP
    stride_options: [1, 3, 5, 10, 20]
    window_size_options: [15, 20, 25, 30]
  
  # Multi-escala (futuro)
  multi_scale:
    enable: false
    short_window: 10       # 5 min - anomalías agudas
    medium_window: 20      # 10 min - degradación gradual  
    long_context: 120      # 60 min - contexto estacional
''',

        "config/model.yaml": '''model:
  # Arquitectura del autoencoder
  architecture:
    encoder_layers: [64, 32, 16]
    decoder_layers: [16, 32, 64]
    activation: "tanh"
    dropout: 0.1
    
  # Parámetros de entrenamiento
  training:
    batch_size: 32
    epochs: 50              # reducido para MVP
    early_stopping: true
    patience: 10
    validation_split: 0.2
    
  # Hiperparámetros
  hyperparameters:
    learning_rate: 0.001
    optimizer: "adam"
    loss: "mse"
    
  # Configuración de modelo
  settings:
    verbose_training: 1
    save_best_only: true
    monitor_metric: "val_loss"
''',

        "config/alerting.yaml": '''alerting:
  # Configuración de threshold
  threshold:
    method: "percentile"     # percentile, fixed, adaptive
    percentile: 95           # para método percentile
    fixed_value: null        # para método fixed
    adaptive_window: 168     # horas para método adaptativo
    
  # Configuración Opsgenie
  opsgenie:
    api_key: "${OPSGENIE_API_KEY}"
    team: "platform-ops"
    base_url: "https://api.opsgenie.com"
    default_priority: "P3"
    
  # Configuración Grafana
  grafana:
    base_url: "${GRAFANA_URL}"
    dashboard_uid: "anomaly-detection"
    default_time_range: "30m"
    refresh_interval: "30s"
    
  # Control de alertas
  rate_limiting:
    min_interval_seconds: 300  # 5 minutos entre alertas
    max_alerts_per_hour: 10
    enable_deduplication: true
''',

        "config/data.yaml": '''data:
  # Configuración Prometheus
  prometheus:
    url: "${PROMETHEUS_URL}"
    token: "${PROMETHEUS_TOKEN}"
    timeout_seconds: 30
    
  # Métricas a recopilar
  metrics:
    # Métricas básicas de TV-over-IP
    queries:
      - name: "request_rate"
        query: "rate(http_requests_total[5m])"
        description: "Request rate per second"
        
      - name: "latency_p95" 
        query: "histogram_quantile(0.95, http_request_duration_seconds)"
        description: "95th percentile latency"
        
      - name: "service_availability"
        query: "up"
        description: "Service availability"
        
      - name: "memory_usage"
        query: "process_resident_memory_bytes / 1024 / 1024 / 1024"
        description: "Memory usage in GB"
        
      - name: "error_rate"
        query: "rate(http_request_errors_total[5m])"
        description: "Error rate per second"
        
      - name: "cpu_usage"
        query: "rate(process_cpu_seconds_total[5m])"
        description: "CPU usage rate"
  
  # Configuración de feature engineering
  features:
    temporal:
      hour_sin: true
      hour_cos: true
      day_of_week: true
      is_weekend: true
      is_night: true
    
    preprocessing:
      normalization: "standard"  # standard, minmax, robust
      outlier_detection: true
      outlier_method: "iqr"      # iqr, zscore, isolation_forest
      outlier_threshold: 3.0
      
    # Configuración de ventana de datos
    collection:
      history_hours: 24          # horas de historial para entrenamiento
      inference_minutes: 30      # minutos de datos para inferencia
      sampling_interval: "30s"   # intervalo de muestreo
''',

        # =============================================================================
        # Source code files
        # =============================================================================

        "src/__init__.py": "",
        "src/utils/__init__.py": "",
        "src/data/__init__.py": "",
        "src/models/__init__.py": "",
        "src/alerting/__init__.py": "",

        "src/utils/config.py": '''import yaml
import os
from typing import Dict, Any
from pathlib import Path

class Config:
    def __init__(self, config_path: str = None):
        """
        Carga configuración desde archivos YAML y variables de entorno
        """
        self.config_path = config_path or "config/"
        self.config = self._load_all_configs()
    
    def _load_all_configs(self) -> Dict[str, Any]:
        """Carga todos los archivos de configuración"""
        configs = {}
        config_dir = Path(self.config_path)
        
        if not config_dir.exists():
            print(f"Warning: Config directory {config_dir} not found")
            return self._get_default_config()
        
        # Cargar archivos YAML
        for config_file in config_dir.glob("*.yaml"):
            with open(config_file, 'r') as f:
                config_name = config_file.stem
                configs[config_name] = yaml.safe_load(f)
        
        # Override con variables de entorno
        configs = self._apply_env_overrides(configs)
        
        return configs
    
    def _apply_env_overrides(self, configs: Dict) -> Dict:
        """Aplica overrides desde variables de entorno"""
        # Prometheus
        if os.getenv('PROMETHEUS_URL'):
            if 'data' not in configs:
                configs['data'] = {}
            configs['data']['prometheus_url'] = os.getenv('PROMETHEUS_URL')
        
        # Opsgenie
        if os.getenv('OPSGENIE_API_KEY'):
            if 'alerting' not in configs:
                configs['alerting'] = {}
            configs['alerting']['opsgenie'] = {'api_key': os.getenv('OPSGENIE_API_KEY')}
        
        return configs
    
    def _get_default_config(self) -> Dict:
        """Configuración por defecto para desarrollo"""
        return {
            'windowing': {
                'window_size': 20,
                'step_size': 30,
                'stride': 20
            },
            'model': {
                'encoder_layers': [64, 32, 16],
                'decoder_layers': [16, 32, 64],
                'batch_size': 32,
                'epochs': 50
            },
            'alerting': {
                'threshold': {'method': 'percentile', 'percentile': 95}
            }
        }
    
    def get(self, key: str, default=None):
        """Obtiene valor de configuración usando dot notation"""
        keys = key.split('.')
        value = self.config
        
        for k in keys:
            if isinstance(value, dict) and k in value:
                value = value[k]
            else:
                return default
        
        return value
''',

        "src/utils/logging.py": '''import logging
import sys
from datetime import datetime

def setup_logger(name: str = "anomaly_detection", level: str = "INFO") -> logging.Logger:
    """
    Configura logger para el sistema
    """
    logger = logging.getLogger(name)
    logger.setLevel(getattr(logging, level.upper()))
    
    if not logger.handlers:
        # Console handler
        handler = logging.StreamHandler(sys.stdout)
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)
    
    return logger
''',

        "src/data/prometheus_client.py": '''import requests
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import List, Dict, Optional

class PrometheusClient:
    """
    Cliente para conectarse a Prometheus y recopilar métricas
    """
    
    def __init__(self, base_url: str, token: str = None):
        self.base_url = base_url.rstrip('/')
        self.session = requests.Session()
        if token:
            self.session.headers.update({'Authorization': f'Bearer {token}'})
    
    def query_range(self, query: str, start_time: datetime, 
                   end_time: datetime, step: str = '30s') -> pd.DataFrame:
        """
        Ejecuta query de rango en Prometheus
        """
        url = f"{self.base_url}/api/v1/query_range"
        
        params = {
            'query': query,
            'start': start_time.timestamp(),
            'end': end_time.timestamp(), 
            'step': step
        }
        
        try:
            response = self.session.get(url, params=params, timeout=30)
            response.raise_for_status()
            
            data = response.json()
            if data['status'] != 'success':
                raise Exception(f"Prometheus query failed: {data.get('error', 'Unknown error')}")
            
            return self._parse_prometheus_response(data['data']['result'])
            
        except requests.exceptions.RequestException as e:
            raise Exception(f"Error connecting to Prometheus: {e}")
    
    def _parse_prometheus_response(self, results: List[Dict]) -> pd.DataFrame:
        """
        Convierte respuesta de Prometheus a DataFrame
        """
        if not results:
            return pd.DataFrame()
        
        dfs = []
        for result in results:
            metric_name = result['metric'].get('__name__', 'unknown')
            values = result['values']
            
            df = pd.DataFrame(values, columns=['timestamp', 'value'])
            df['timestamp'] = pd.to_datetime(df['timestamp'], unit='s')
            df['value'] = pd.to_numeric(df['value'], errors='coerce')
            df['metric'] = metric_name
            
            dfs.append(df)
        
        if dfs:
            combined = pd.concat(dfs, ignore_index=True)
            pivoted = combined.pivot(index='timestamp', columns='metric', values='value')
            pivoted.reset_index(inplace=True)
            return pivoted.fillna(0)
        
        return pd.DataFrame()
    
    def get_tv_metrics(self, hours_back: int = 24) -> pd.DataFrame:
        """
        Recopila métricas típicas de TV-over-IP
        """
        end_time = datetime.now()
        start_time = end_time - timedelta(hours=hours_back)
        
        queries = [
            'rate(http_requests_total[5m])',
            'histogram_quantile(0.95, http_request_duration_seconds)',
            'up',
            'process_resident_memory_bytes',
            'rate(http_request_errors_total[5m])',
        ]
        
        all_metrics = []
        for query in queries:
            try:
                df = self.query_range(query, start_time, end_time)
                if not df.empty:
                    all_metrics.append(df)
            except Exception as e:
                print(f"Warning: Failed to fetch query '{query}': {e}")
        
        if all_metrics:
            combined = all_metrics[0]
            for df in all_metrics[1:]:
                combined = combined.merge(df, on='timestamp', how='outer')
            
            return combined.sort_values('timestamp').fillna(method='ffill').fillna(0)
        
        return pd.DataFrame()
''',

        "src/data/preprocessor.py": '''import pandas as pd
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
''',

        "src/data/windowing.py": '''import numpy as np
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
''',

        "src/models/lstm_autoencoder.py": '''import tensorflow as tf
from tensorflow import keras
from tensorflow.keras import layers
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
        
        # Decoder
        for i, units in enumerate(self.decoder_layers):
            return_seq = i < len(self.decoder_layers) - 1
            x = layers.LSTM(units, return_sequences=return_seq, 
                          name=f'decoder_lstm_{i}')(x)
            x = layers.Dropout(self.dropout)(x)
        
        # Output layer
        outputs = layers.Dense(self.input_shape[1], activation='linear')(x)
        outputs = layers.Reshape(self.input_shape)(outputs)
        
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
        self.model.save(filepath)
    
    def load(self, filepath: str):
        """Carga modelo previamente entrenado"""
        self.model = keras.models.load_model(filepath)
        
        # Reconstruir encoder
        latent_layer = self.model.get_layer('latent')
        self.encoder = keras.Model(
            inputs=self.model.input,
            outputs=latent_layer.output
        )
''',

        "src/alerting/detector.py": '''import numpy as np
import pandas as pd
from typing import Dict, List
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
    
    def get_recent_detections(self, hours: int = 24) -> List[Dict]:
        """
        Obtiene detecciones recientes
        """
        cutoff_time = datetime.now().timestamp() - (hours * 3600)
        
        recent = []
        for detection in self.detection_history:
            detection_time = datetime.fromisoformat(detection['timestamp']).timestamp()
            if detection_time > cutoff_time:
                recent.append(detection)
        
        return recent
    
    def get_anomaly_summary(self, hours: int = 24) -> Dict:
        """
        Resumen de anomalías en período especificado
        """
        recent = self.get_recent_detections(hours)
        anomalies = [d for d in recent if d.get('is_anomaly', False)]
        
        return {
            'total_detections': len(recent),
            'anomalies_count': len(anomalies),
            'anomaly_rate': len(anomalies) / max(len(recent), 1),
            'avg_reconstruction_error': np.mean([d['reconstruction_error'] for d in recent]) if recent else 0,
            'max_reconstruction_error': max([d['reconstruction_error'] for d in recent]) if recent else 0,
            'period_hours': hours
        }
''',

        "src/alerting/opsgenie_client.py": '''import requests
import json
from typing import Dict
from datetime import datetime

class OpsgenieClient:
    """
    Cliente para enviar alertas a Opsgenie
    """
    
    def __init__(self, api_key: str, base_url: str = "https://api.opsgenie.com"):
        self.api_key = api_key
        self.base_url = base_url.rstrip('/')
        self.headers = {
            'Authorization': f'GenieKey {api_key}',
            'Content-Type': 'application/json'
        }
    
    def create_alert(self, detection_result: Dict, grafana_link: str = None) -> Dict:
        """
        Crea alerta en Opsgenie basada en detección de anomalía
        """
        if not detection_result.get('is_anomaly', False):
            return {'status': 'skipped', 'reason': 'Not an anomaly'}
        
        error_value = detection_result['reconstruction_error']
        threshold = detection_result['threshold']
        confidence = detection_result.get('confidence', 0)
        
        description = f"""
Anomalía detectada en servicio TV-over-IP

🔍 Detalles:
- Error de reconstrucción: {error_value:.4f}
- Umbral configurado: {threshold:.4f} 
- Confianza: {confidence:.2f}
- Timestamp: {detection_result['timestamp']}

📊 Métricas afectadas:
{self._format_metrics_comparison(detection_result)}
        """.strip()
        
        alert_payload = {
            'message': 'Anomalía detectada en TV-over-IP',
            'description': description,
            'priority': self._determine_priority(confidence),
            'tags': ['anomaly-detection', 'tv-over-ip', 'lstm-autoencoder'],
            'details': {
                'reconstruction_error': error_value,
                'threshold': threshold,
                'confidence': confidence,
                'detection_time': detection_result['timestamp'],
                'service': 'tv-over-ip'
            }
        }
        
        if grafana_link:
            alert_payload['description'] += f"\\n\\n📈 Ver en Grafana: {grafana_link}"
            alert_payload['details']['grafana_link'] = grafana_link
        
        try:
            response = requests.post(
                f"{self.base_url}/v2/alerts",
                headers=self.headers,
                data=json.dumps(alert_payload),
                timeout=10
            )
            response.raise_for_status()
            
            return {
                'status': 'success',
                'alert_id': response.json().get('requestId'),
                'response': response.json()
            }
            
        except requests.exceptions.RequestException as e:
            return {
                'status': 'error',
                'error': str(e),
                'payload': alert_payload
            }
    
    def _determine_priority(self, confidence: float) -> str:
        """Determina prioridad basada en confianza"""
        if confidence > 2.0:
            return 'P1'
        elif confidence > 1.0:
            return 'P2'
        elif confidence > 0.5:
            return 'P3'
        else:
            return 'P4'
    
    def _format_metrics_comparison(self, detection_result: Dict) -> str:
        """Formatea comparación de métricas"""
        if 'feature_columns' not in detection_result:
            return "Datos de métricas no disponibles"
        
        original = detection_result.get('original_values', [])
        reconstructed = detection_result.get('reconstructed_values', [])
        features = detection_result['feature_columns']
        
        if not original or not reconstructed or not features:
            return "Datos de comparación no disponibles"
        
        # Mostrar solo las últimas mediciones
        if len(original) > 0 and len(original[0]) > 0:
            last_original = original[-1] if isinstance(original[0], list) else original
            last_reconstructed = reconstructed[-1] if isinstance(reconstructed[0], list) else reconstructed
            
            comparison = []
            for i, feature in enumerate(features[:min(len(features), len(last_original))]):
                orig_val = last_original[i] if i < len(last_original) else 0
                recon_val = last_reconstructed[i] if i < len(last_reconstructed) else 0
                diff = abs(orig_val - recon_val)
                comparison.append(f"  {feature}: {orig_val:.3f} → {recon_val:.3f} (diff: {diff:.3f})")
            
            return "\\n".join(comparison[:5])
        
        return "No se pudieron procesar las métricas"
''',

        "src/alerting/grafana_links.py": '''from datetime import datetime, timedelta
from urllib.parse import quote

class GrafanaLinkGenerator:
    """
    Generador de enlaces contextuales a dashboards de Grafana
    """
    
    def __init__(self, base_url: str, dashboard_uid: str = None):
        self.base_url = base_url.rstrip('/')
        self.dashboard_uid = dashboard_uid or "anomaly-detection"
    
    def generate_anomaly_link(self, detection_time: str, 
                            time_range_minutes: int = 30) -> str:
        """
        Genera enlace a Grafana centrado en el tiempo de la anomalía
        """
        detection_dt = datetime.fromisoformat(detection_time.replace('Z', '+00:00'))
        
        start_time = detection_dt - timedelta(minutes=time_range_minutes // 2)
        end_time = detection_dt + timedelta(minutes=time_range_minutes // 2)
        
        start_ms = int(start_time.timestamp() * 1000)
        end_ms = int(end_time.timestamp() * 1000)
        
        params = f"from={start_ms}&to={end_ms}&refresh=30s"
        
        annotation = f"anomaly_detected_at_{int(detection_dt.timestamp())}"
        params += f"&var-annotation={quote(annotation)}"
        
        url = f"{self.base_url}/d/{self.dashboard_uid}/tv-over-ip-anomaly-detection?{params}"
        
        return url
''',

        # =============================================================================
        # Scripts
        # =============================================================================

        "scripts/setup.py": '''#!/usr/bin/env python3

"""
Script de configuración inicial para el sistema de detección de anomalías
"""

import os
import sys
import subprocess
from pathlib import Path

def create_directory_structure():
    """Crea la estructura de directorios del proyecto"""
    print("Creating directory structure...")
    
    directories = [
        "src/data", "src/models", "src/alerting", "src/utils",
        "config", "scripts", "models", "logs", 
        "tests/unit", "tests/integration", "docs"
    ]
    
    for directory in directories:
        Path(directory).mkdir(parents=True, exist_ok=True)
        
        if directory.startswith("src/"):
            init_file = Path(directory) / "__init__.py"
            init_file.touch()
    
    print("✅ Directory structure created")

def install_python_dependencies():
    """Instala dependencias de Python"""
    print("Installing Python dependencies...")
    
    try:
        subprocess.run([
            sys.executable, "-m", "pip", "install", "-r", "requirements.txt"
        ], check=True)
        print("✅ Python dependencies installed")
        return True
    except subprocess.CalledProcessError:
        print("❌ Failed to install Python dependencies")
        return False

def main():
    """Función principal de setup"""
    print("=== Anomaly Detection System Setup ===")
    
    create_directory_structure()
    
    if install_python_dependencies():
        print("\\n🎉 Setup completed successfully!")
        print("\\nNext steps:")
        print("1. Configure .env file")
        print("2. Train model: python scripts/train.py")
        print("3. Start detection: python scripts/inference.py")
    else:
        print("\\n❌ Setup failed")
        sys.exit(1)

if __name__ == "__main__":
    main()
''',

        "scripts/train.py": '''#!/usr/bin/env python3

"""
Script de entrenamiento para el MVP
"""

import os
import sys
import numpy as np
import pandas as pd
from datetime import datetime, timedelta

# Agregar src al path
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'src'))

from utils.config import Config
from utils.logging import setup_logger
from data.prometheus_client import PrometheusClient
from data.preprocessor import DataPreprocessor
from data.windowing import WindowGenerator
from models.lstm_autoencoder import LSTMAutoencoder

def generate_synthetic_data() -> pd.DataFrame:
    """
    Genera datos sintéticos para desarrollo
    """
    start_time = datetime.now() - timedelta(days=7)
    timestamps = pd.date_range(start=start_time, periods=20160, freq='30S')
    
    np.random.seed(42)
    n_points = len(timestamps)
    
    # Patrón base con ciclo diario
    hours = np.array([ts.hour for ts in timestamps])
    daily_pattern = 0.5 + 0.3 * np.sin(2 * np.pi * hours / 24)
    
    data = {
        'timestamp': timestamps,
        'request_rate': daily_pattern * 1000 + np.random.normal(0, 50, n_points),
        'latency_p95': daily_pattern * 200 + 100 + np.random.normal(0, 20, n_points),
        'memory_usage': daily_pattern * 0.7 + 0.3 + np.random.normal(0, 0.05, n_points),
        'error_rate': np.random.exponential(0.01, n_points),
        'cpu_usage': daily_pattern * 0.8 + 0.2 + np.random.normal(0, 0.1, n_points)
    }
    
    # Asegurar valores positivos
    for col in ['request_rate', 'latency_p95', 'error_rate']:
        data[col] = np.maximum(data[col], 0)
    
    data['memory_usage'] = np.clip(data['memory_usage'], 0, 1)
    data['cpu_usage'] = np.clip(data['cpu_usage'], 0, 1)
    
    return pd.DataFrame(data)

def main():
    """
    Pipeline completo de entrenamiento para MVP
    """
    logger = setup_logger()
    logger.info("=== Iniciando entrenamiento MVP ===")
    
    config = Config()
    
    # 1. Recopilar datos
    logger.info("Recopilando datos...")
    
    prometheus_url = config.get('data.prometheus_url')
    if prometheus_url:
        client = PrometheusClient(prometheus_url)
        df = client.get_tv_metrics(hours_back=24*7)
    else:
        logger.warning("No Prometheus URL configured, generating synthetic data")
        df = generate_synthetic_data()
    
    if df.empty:
        logger.error("No data available for training")
        return
    
    logger.info(f"Data shape: {df.shape}")
    
    # 2. Preprocesamiento
    logger.info("Preprocessing data...")
    preprocessor = DataPreprocessor(scaler_type='standard')
    df_processed = preprocessor.fit_transform(df)
    
    os.makedirs('models/', exist_ok=True)
    preprocessor.save_scaler('models/preprocessor.joblib')
    
    # 3. Crear ventanas deslizantes
    logger.info("Creating sliding windows...")
    window_size = config.get('windowing.window_size', 20)
    stride = config.get('windowing.stride', 20)
    
    windower = WindowGenerator(window_size=window_size, stride=stride)
    X, y = windower.create_sequences(df_processed)
    
    logger.info(f"Generated {X.shape[0]} sequences of shape {X.shape[1:]}")
    
    # 4. Split train/validation
    split_idx = int(0.8 * len(X))
    X_train, X_val = X[:split_idx], X[split_idx:]
    
    logger.info(f"Training samples: {X_train.shape[0]}, Validation samples: {X_val.shape[0]}")
    
    # 5. Entrenar modelo
    logger.info("Training LSTM Autoencoder...")
    
    input_shape = (X_train.shape[1], X_train.shape[2])
    encoder_layers = config.get('model.encoder_layers', [64, 32, 16])
    decoder_layers = config.get('model.decoder_layers', [16, 32, 64])
    
    model = LSTMAutoencoder(
        input_shape=input_shape,
        encoder_layers=encoder_layers,
        decoder_layers=decoder_layers
    )
    
    epochs = config.get('model.epochs', 50)
    batch_size = config.get('model.batch_size', 32)
    
    history = model.train(
        X_train=X_train,
        X_val=X_val,
        epochs=epochs,
        batch_size=batch_size
    )
    
    # 6. Guardar modelo
    model.save('models/lstm_autoencoder.h5')
    logger.info("Model saved to models/lstm_autoencoder.h5")
    
    # 7. Calcular threshold
    logger.info("Computing anomaly threshold...")
    reconstruction_errors = model.compute_reconstruction_error(X_val)
    
    threshold_method = config.get('alerting.threshold.method', 'percentile')
    if threshold_method == 'percentile':
        percentile = config.get('alerting.threshold.percentile', 95)
        threshold = np.percentile(reconstruction_errors, percentile)
    else:
        threshold = reconstruction_errors.mean() + 2 * reconstruction_errors.std()
    
    np.save('models/anomaly_threshold.npy', threshold)
    logger.info(f"Anomaly threshold: {threshold:.4f}")
    
    # 8. Estadísticas finales
    final_loss = history['loss'][-1]
    final_val_loss = history['val_loss'][-1] if 'val_loss' in history else None
    
    logger.info(f"Final training loss: {final_loss:.4f}")
    if final_val_loss:
        logger.info(f"Final validation loss: {final_val_loss:.4f}")
    
    logger.info("=== Entrenamiento completado ===")

if __name__ == "__main__":
    main()
''',

        "scripts/inference.py": '''#!/usr/bin/env python3

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
            if os.path.exists('models/lstm_autoencoder.h5'):
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
            freq='30S'
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
        print("\\nShutdown requested by user")
    except Exception as e:
        print(f"Service failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
''',

        "scripts/deploy.sh": '''#!/bin/bash

set -e

echo "=== Anomaly Detection System Deployment Script ==="

ENVIRONMENT=${1:-"development"}
echo "Environment: $ENVIRONMENT"

# Verificar dependencias
if ! command -v docker &> /dev/null; then
    echo "❌ Docker is not installed"
    exit 1
fi

if ! command -v docker-compose &> /dev/null; then
    echo "❌ Docker Compose is not installed"  
    exit 1
fi

# Crear .env si no existe
if [[ ! -f .env ]]; then
    cp .env.example .env
    echo "📝 Created .env file - please configure your settings"
fi

# Construir y deployar
echo "Building and deploying..."
docker-compose down

if [[ "$ENVIRONMENT" == "development" ]]; then
    docker-compose --profile dev up -d
else
    docker-compose up -d anomaly-detection
fi

echo "✅ Deployment completed!"
echo "View logs: docker logs -f tv-anomaly-detector"
''',

        # =============================================================================
        # Documentation
        # =============================================================================

        "docs/installation.md": '''# Guía de Instalación

## Requisitos del Sistema

- Python 3.8+
- Docker & Docker Compose
- 8GB RAM mínimo
- Acceso a Prometheus (opcional)

## Instalación

### 1. Clonar Repositorio

```bash
git clone https://github.com/tu-usuario/tv-anomaly-detection.git
cd tv-anomaly-detection
```

### 2. Setup Automático

```bash
python scripts/setup.py
```

### 3. Configuración

```bash
cp .env.example .env
# Editar .env con tus configuraciones
```

### 4. Entrenamiento

```bash
python scripts/train.py
```

### 5. Inferencia

```bash
python scripts/inference.py
```
''',

        "docs/troubleshooting.md": '''# Troubleshooting

## Problemas Comunes

### Error: "Model not found"
```bash
# Solución: entrenar modelo primero
python scripts/train.py
```

### Error: "Prometheus connection failed"
```bash
# Verificar conectividad
curl http://your-prometheus:9090/api/v1/status/config
```

### Alta tasa de falsos positivos
```yaml
# Ajustar umbral en config/alerting.yaml
alerting:
  threshold:
    percentile: 98  # más restrictivo
```

## Logs

```bash
# Ver logs del contenedor
docker logs -f tv-anomaly-detector

# Ver logs de entrenamiento
cat logs/training.log
```
''',

        # =============================================================================
        # Tests básicos
        # =============================================================================

        "tests/__init__.py": "",
        "tests/unit/__init__.py": "",
        "tests/integration/__init__.py": "",

        "tests/unit/test_config.py": '''import pytest
import os
from src.utils.config import Config

def test_config_default():
    """Test configuración por defecto"""
    config = Config(config_path="nonexistent")
    
    assert config.get('windowing.window_size') == 20
    assert config.get('model.batch_size') == 32

def test_config_get():
    """Test método get con dot notation"""
    config = Config(config_path="nonexistent")
    
    assert config.get('windowing.window_size') == 20
    assert config.get('nonexistent.key', 'default') == 'default'
''',

        # =============================================================================
        # GitHub Actions
        # =============================================================================

        ".github/workflows/ci.yml": '''name: CI Pipeline

on:
  push:
    branches: [ main, develop ]
  pull_request:
    branches: [ main ]

jobs:
  test:
    runs-on: ubuntu-latest
    strategy:
      matrix:
        python-version: [3.8, 3.9]

    steps:
    - uses: actions/checkout@v3
    
    - name: Set up Python ${{ matrix.python-version }}
      uses: actions/setup-python@v3
      with:
        python-version: ${{ matrix.python-version }}
    
    - name: Install dependencies
      run: |
        python -m pip install --upgrade pip
        pip install -r requirements.txt
        pip install pytest
    
    - name: Run tests
      run: |
        pytest tests/ -v
    
    - name: Lint with flake8
      run: |
        pip install flake8
        flake8 src/ --count --select=E9,F63,F7,F82 --show-source --statistics

  docker:
    runs-on: ubuntu-latest
    needs: test
    
    steps:
    - uses: actions/checkout@v3
    
    - name: Build Docker image
      run: |
        docker build -t tv-anomaly-detection:test .
    
    - name: Test Docker container
      run: |
        docker run --rm tv-anomaly-detection:test python -c "import src.utils.config; print('Import test passed')"
'''
    }
    
    return files_content

def create_project_structure():
    """Crea toda la estructura del proyecto"""
    print("🚀 Creating TV Anomaly Detection project structure...")
    
    # Crear directorios
    directories = [
        "src/data", "src/models", "src/alerting", "src/utils",
        "config", "scripts", "models", "logs", "tests/unit", 
        "tests/integration", "docs", ".github/workflows"
    ]
    
    for directory in directories:
        Path(directory).mkdir(parents=True, exist_ok=True)
    
    # Crear archivos
    files_content = create_file_structure()
    
    for file_path, content in files_content.items():
        file_obj = Path(file_path)
        file_obj.parent.mkdir(parents=True, exist_ok=True)
        
        with open(file_obj, 'w', encoding='utf-8') as f:
            f.write(content)
        
        # Hacer ejecutables los scripts
        if file_path.startswith('scripts/') and file_path.endswith(('.sh', '.py')):
            file_obj.chmod(0o755)
    
    print("✅ Project structure created successfully!")

def initialize_git_repo():
    """Inicializa repositorio Git"""
    try:
        if not Path('.git').exists():
            subprocess.run(['git', 'init'], check=True)
            print("✅ Git repository initialized")
        
        subprocess.run(['git', 'add', '.'], check=True)
        subprocess.run(['git', 'commit', '-m', 'Initial commit: MVP Anomaly Detection System'], check=True)
        print("✅ Initial commit created")
        
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ Git initialization failed: {e}")
        return False

def main():
    """Función principal"""
    print("=" * 60)
    print("🎯 TV ANOMALY DETECTION - GITHUB REPO GENERATOR")
    print("=" * 60)
    
    # Verificar si estamos en directorio vacío o crear nuevo
    if len(list(Path('.').iterdir())) > 0:
        response = input("\\n⚠️  Current directory is not empty. Continue? (y/N): ")
        if response.lower() != 'y':
            print("Aborted.")
            return
    
    try:
        # Crear estructura del proyecto
        create_project_structure()
        
        # Inicializar Git
        initialize_git_repo()
        
        print("\\n🎉 SUCCESS! Project ready for GitHub!")
        print("\\n📋 Next steps:")
        print("1. Create repository on GitHub:")
        print("   https://github.com/new")
        print("\\n2. Add remote and push:")
        print("   git remote add origin https://github.com/tu-usuario/tv-anomaly-detection.git")
        print("   git branch -M main")
        print("   git push -u origin main")
        print("\\n3. Configure environment:")
        print("   cp .env.example .env")
        print("   # Edit .env with your settings")
        print("\\n4. Start development:")
        print("   python scripts/setup.py")
        print("   python scripts/train.py")
        print("\\n📚 Documentation: docs/")
        print("🐛 Issues: Enable on GitHub repository")
        
    except Exception as e:
        print(f"\\n❌ Error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
