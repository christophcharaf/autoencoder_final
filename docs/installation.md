# Guía de Instalación

## Requisitos del Sistema

- Python 3.8+
- Docker & Docker Compose
- 8GB RAM mínimo (2GB reservados para el contenedor de detección)
- Acceso a Prometheus (incluido en el entorno de desarrollo)

## Arquitectura del Sistema

```
┌──────────────┐     ┌──────────────┐     ┌──────────────┐
│ Mock Service │────▶│  Prometheus  │────▶│   Anomaly    │
│  (Flask)     │     │  (Scraping)  │     │  Detector    │
│  :8000       │     │  :9090       │     │  (LSTM AE)   │
└──────────────┘     └──────────────┘     └──────┬───────┘
                            │                     │
                     ┌──────▼──────┐        ┌─────▼──────┐
                     │   Grafana   │        │  Opsgenie  │
                     │   :3000     │        │  (Alertas) │
                     └─────────────┘        └────────────┘
```

## Instalación

### 1. Clonar Repositorio

```bash
git clone https://github.com/tu-usuario/tv-anomaly-detection.git
cd tv-anomaly-detection
```

### 2. Configuración de Variables de Entorno

```bash
cp .env.example .env
```

Editar `.env` con las configuraciones necesarias:

```bash
# Requerido para alertas (opcional si solo se desea detección local)
OPSGENIE_API_KEY=tu-api-key

# Token de Prometheus (si requiere autenticación)
PROMETHEUS_TOKEN=

# URL de Grafana para enlaces en alertas (usar localhost para desarrollo)
GRAFANA_URL=http://localhost:3000
```

### 3. Levantar Entorno de Desarrollo

El entorno de desarrollo incluye: mock service, Prometheus, Grafana y el detector.

```bash
# Levantar todos los servicios (desarrollo)
docker-compose --profile dev up -d

# Verificar que todos los servicios estén corriendo
docker-compose ps
```

**Servicios disponibles:**

| Servicio | Puerto | Descripción |
|----------|--------|-------------|
| Mock Service | `localhost:8000` | Servicio simulado de TV-over-IP con métricas Prometheus |
| Prometheus | `localhost:9090` | Recolección y almacenamiento de métricas |
| Grafana | `localhost:3000` | Visualización de métricas (usuario: `admin`, contraseña: `admin`) |
| Anomaly Detector | - | Detección de anomalías con LSTM Autoencoder |

### 4. Entrenamiento del Modelo

El entrenamiento puede usar datos reales de Prometheus o generar datos sintéticos si no hay suficiente historial disponible.

```bash
# Entrenamiento (usa datos sintéticos como fallback si Prometheus no tiene suficiente historial)
python scripts/train.py
```

**Nota:** Para un modelo óptimo, se recomienda tener al menos 7 días de datos reales en Prometheus. Si el mock service acaba de iniciarse, el script generará datos sintéticos automáticamente. Una vez que Prometheus tenga suficiente historial, se puede reentrenar con datos reales para mayor precisión.

**Archivos generados por el entrenamiento:**

| Archivo | Descripción |
|---------|-------------|
| `models/lstm_autoencoder.weights.h5` | Pesos del modelo LSTM Autoencoder |
| `models/lstm_autoencoder_config.json` | Configuración de arquitectura |
| `models/preprocessor.joblib` | Scaler de normalización (StandardScaler) |
| `models/anomaly_threshold.npy` | Umbral de detección calculado |
| `evaluation/model_evaluation.png` | Gráficas de evaluación del modelo |

### 5. Iniciar Detección de Anomalías

```bash
# Reconstruir el contenedor de detección con el modelo entrenado
docker-compose build anomaly-detection

# Reiniciar el servicio
docker-compose stop anomaly-detection && docker-compose rm -f anomaly-detection
docker-compose up -d anomaly-detection

# Verificar logs
docker logs -f tv-anomaly-detector
```

**Importante:** Después de cambios en código o configuración, siempre ejecutar el ciclo completo de `stop → rm → up` para garantizar que los cambios se apliquen correctamente. Un simple `docker-compose restart` puede no reflejar cambios en variables de entorno o código.

### 6. Verificar Funcionamiento

```bash
# Ver estado del detector
docker logs tv-anomaly-detector --tail 20

# Inyectar una anomalía de prueba
curl -X POST http://localhost:8000/anomaly \
  -H "Content-Type: application/json" \
  -d '{"type": "latency_spike", "duration": 120, "severity": "high"}'

# Ver anomalías activas en el mock service
curl http://localhost:8000/anomaly

# Limpiar anomalías
curl -X POST http://localhost:8000/anomaly/clear
```

**Tipos de anomalías disponibles para inyección:**

| Tipo | Descripción |
|------|-------------|
| `latency_spike` | Incremento súbito en latencia p95 |
| `error_burst` | Ráfaga de errores HTTP |
| `memory_spike` | Incremento en uso de memoria |
| `traffic_drop` | Caída abrupta en tasa de peticiones |

## Configuración

### Archivos de Configuración

| Archivo | Descripción |
|---------|-------------|
| `config/data.yaml` | Conexión a Prometheus, métricas, ventana de datos |
| `config/model.yaml` | Arquitectura del LSTM Autoencoder, hiperparámetros |
| `config/alerting.yaml` | Umbrales, Opsgenie, Grafana, deduplicación |
| `config/windowing.yaml` | Ventana deslizante (tamaño, paso, stride) |

### Parámetros Clave

#### Detección (`config/data.yaml`)
```yaml
collection:
  history_hours: 168        # Historial para entrenamiento (7 días)
  inference_minutes: 5      # Ventana de datos para inferencia
  sampling_interval: "30s"  # Intervalo de muestreo
```

#### Umbral (`config/alerting.yaml`)
```yaml
threshold:
  method: "percentile"      # percentile, fixed, adaptive
  percentile: 99.5           # Percentil del error de reconstrucción
```

#### Deduplicación de Alertas (`config/alerting.yaml`)
```yaml
rate_limiting:
  enable_deduplication: true
  min_confidence: 0.25                # Margen mínimo sobre el umbral (25%)
  heartbeat_interval_seconds: 180     # Log de estado cada 3 minutos
  escalation_threshold_minutes: 30    # Re-alertar si persiste 30+ min
  escalation_interval_minutes: 15     # Re-alertar cada 15 min después
  send_resolved_notification: true    # Notificar cuando se resuelve
```

#### Modelo (`config/model.yaml`)
```yaml
architecture:
  encoder_layers: [64, 32, 16]
  decoder_layers: [16, 32, 64]
  activation: "tanh"
  dropout: 0.1
training:
  batch_size: 32
  epochs: 30
  early_stopping: true
  patience: 10
```

## Despliegue en Producción

### Variables de Entorno

```bash
# En producción, configurar la URL real de Grafana
GRAFANA_URL=https://grafana.tu-empresa.com

# API Key de Opsgenie para alertas
OPSGENIE_API_KEY=tu-api-key-real

# Token de Prometheus si requiere autenticación
PROMETHEUS_TOKEN=tu-token
```

### Despliegue Solo del Detector (sin mock service)

```bash
# Solo el detector conectado a Prometheus existente
docker-compose up -d anomaly-detection
```

Ajustar `config/data.yaml` con la URL de Prometheus de producción y las queries PromQL correspondientes al servicio real.
