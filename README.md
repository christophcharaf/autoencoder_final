# Sistema de Detección de Anomalías TV-over-IP con LSTM Autoencoder

[![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![Docker](https://img.shields.io/badge/docker-ready-brightgreen.svg)](https://www.docker.com/)
[![License: Academic](https://img.shields.io/badge/license-Academic-yellow.svg)](LICENSE)

Sistema de detección de anomalías en tiempo real para servicios de TV-over-IP utilizando deep learning. Implementa un autoencoder LSTM con sistema inteligente de deduplicación de alertas, monitoreo continuo, y escalación automática.

## 🎯 Características Principales

### Core Features
✅ **Recolección de métricas** desde Prometheus con agregación inteligente  
✅ **Preprocesamiento avanzado** con feature engineering temporal (6 features)  
✅ **Modelo LSTM Autoencoder** con arquitectura encoder-decoder  
✅ **Sistema de deduplicación de alertas** con UUID tracking y state machine  
✅ **Alertas automáticas** via Opsgenie con escalación inteligente  
✅ **Enlaces contextuales** a dashboards Grafana  
✅ **Containerización completa** con Docker Compose  
✅ **Configuración flexible** via YAML  

### Advanced Features
🚀 **Generador sintético compartido** con el mock service (`traffic_simulation_core.py`)  
🚀 **Readiness guard** para no inferir sobre ventanas Prometheus incompletas o stale  
🚀 **Confirmación de alertas** tras 2 ciclos anomalos consecutivos  
🚀 **Heartbeat logs** configurables para anomalías en curso (default: 30s)  
🚀 **Escalación automática** después de 30 minutos de persistencia  
🚀 **Notificaciones de resolución** cuando anomalías se resuelven  
🚀 **Filtrado por confianza** (25% sobre threshold para reducir falsos positivos)  
🚀 **Peak error tracking** para análisis post-incidente  
🚀 **Mock service** para desarrollo y testing  
🚀 **Alineación de ventanas** (20 × 30s = 10 min) sin zero-padding en producción  

## 📋 Requisitos

- Python 3.8+
- Docker & Docker Compose
- 8GB RAM mínimo (2GB para el contenedor de detección)
- Acceso a Prometheus (incluido en entorno dev)

## 🚀 Instalación Rápida

### Opción 1: Entorno de Desarrollo Completo (Recomendado)

Incluye mock service, Prometheus, Grafana y el detector.

```bash
# 1. Clonar repositorio
git clone https://github.com/tu-usuario/tv-anomaly-detection.git
cd tv-anomaly-detection

# 2. Configurar variables de entorno
cp .env.example .env
# Editar .env con tu API key de Opsgenie (opcional para desarrollo)
# Docker Compose lee .env automáticamente; scripts Python locales usan variables exportadas.

# 3. Levantar infraestructura de desarrollo
docker-compose --profile dev up -d --build mock-service prometheus grafana

# 4. Entrenar el modelo
# Para entrenamiento sintético local reproducible:
PROMETHEUS_URL=disabled PYTHONUNBUFFERED=1 python scripts/train.py

# 5. Levantar o reconstruir el detector
docker-compose --profile dev up -d --build anomaly-detection

# 6. Verificar logs
docker logs -f tv-anomaly-detector
```

**Servicios disponibles:**
- Mock Service: `http://localhost:8000` (métricas + POST /anomaly para inyección)
- Prometheus: `http://localhost:9090`
- Grafana: `http://localhost:3000` (admin/admin) — dashboard "TV-over-IP Metrics" auto-provisionado

### Opción 2: Solo Detector (Producción)

Conecta a Prometheus existente.

```bash
# Ajustar PROMETHEUS_URL en el entorno o en docker-compose.yml
# Nota: las variables de entorno sobrescriben config/data.yaml
PROMETHEUS_URL=https://prometheus.example.com docker-compose up -d anomaly-detection
```

## 📁 Estructura del Proyecto

```
autoencoder_final/
├── src/                          # Código fuente
│   ├── data/                     # Pipeline de datos
│   │   ├── prometheus_client.py  # Cliente Prometheus con agregación
│   │   ├── preprocessor.py       # Feature engineering y normalización
│   │   ├── synthetic_data.py     # Fallback sintético alineado a PromQL/mock
│   │   └── windowing.py          # Sliding window generator
│   ├── models/                   # Arquitectura del modelo
│   │   └── lstm_autoencoder.py   # LSTM Autoencoder
│   ├── alerting/                 # Sistema de alertas
│   │   ├── detector.py           # Lógica de detección
│   │   ├── opsgenie_client.py    # Integración Opsgenie
│   │   └── grafana_links.py      # Generador de enlaces
│   └── utils/                    # Utilidades
│       ├── config.py             # Gestor de configuración
│       └── logging.py            # Setup de logging
├── config/                       # Configuración YAML
│   ├── model.yaml                # Arquitectura e hiperparámetros
│   ├── windowing.yaml            # Ventanas deslizantes
│   ├── alerting.yaml             # Umbrales y deduplicación
│   └── data.yaml                 # Prometheus y métricas
├── scripts/                      # Scripts principales
│   ├── train.py                  # Entrenamiento del modelo
│   ├── inference.py              # Detección en tiempo real
│   ├── evaluate_model.py         # Evaluación, plots y CSV de iteraciones
│   └── tune_model.py             # Tuning seguro en evaluation/tuning_runs/
├── mock_service/                 # Servicio simulado para dev
│   ├── app.py                    # Flask app con métricas
│   ├── traffic_simulation_core.py # Simulación compartida mock/sintético
│   └── Dockerfile                # Imagen Docker
├── grafana/                      # Dashboards y provisioning
│   ├── dashboards/               # Dashboard JSON
│   └── provisioning/             # Datasources config
├── models/                       # Modelos entrenados (generado)
│   ├── lstm_autoencoder.weights.h5
│   ├── lstm_autoencoder_config.json
│   ├── preprocessor.joblib
│   └── anomaly_threshold.npy
├── docs/                         # Documentación
│   ├── installation.md           # Guía de instalación
│   └── troubleshooting.md        # Resolución de problemas
├── TROUBLESHOOTING_JOURNAL.md    # Diario de issues y fixes
├── docker-compose.yml            # Orquestación de servicios
├── Dockerfile                    # Imagen del detector
└── prometheus.yml                # Configuración de scraping
```

## 🎮 Uso

### Entrenamiento del Modelo

```bash
# Entrena con datos de Prometheus (o sintéticos como fallback)
python scripts/train.py

# Archivos generados:
# - models/lstm_autoencoder.weights.h5 (pesos del modelo)
# - models/preprocessor.joblib (preprocessor con fixed_minmax scaler)
# - models/anomaly_threshold.npy (threshold calculado)

# Evaluar modelo (genera evaluation/model_evaluation.png y CSV)
python scripts/evaluate_model.py           # Interactivo (muestra ventana)
python scripts/evaluate_model.py --headless  # Use --headless para CI/automación

# Sweep rápido de thresholds sin reentrenar
python scripts/evaluate_model.py --headless --sweep-thresholds 95,97.5,99,99.5,99.9

# Tuning seguro: candidatos se guardan bajo evaluation/tuning_runs/
python scripts/tune_model.py --quick --max-candidates 5 --verbose 0
```

### Detección en Tiempo Real

El servicio corre automáticamente en Docker. Para ver logs:

```bash
# Ver logs del detector
docker logs -f tv-anomaly-detector

# Ver últimas 50 líneas
docker logs tv-anomaly-detector --tail 50

# Filtrar solo alertas
docker logs tv-anomaly-detector 2>&1 | grep -E "(NEW ANOMALY|RESOLVED|ESCALATION)"
```

### Inyección de Anomalías (Testing)

```bash
# Pico de latencia (120 segundos)
curl -X POST http://localhost:8000/anomaly \
  -H "Content-Type: application/json" \
  -d '{"type": "latency_spike", "duration": 120}'

# Ráfaga de errores
curl -X POST http://localhost:8000/anomaly \
  -H "Content-Type: application/json" \
  -d '{"type": "error_burst", "duration": 120}'

# Verificar anomalías activas
curl http://localhost:8000/anomaly

# Limpiar anomalías
curl -X POST http://localhost:8000/anomaly/clear
```

**Tipos de anomalías disponibles:**
- `latency_spike`: Incremento súbito en latencia p95
- `error_burst`: Ráfaga de errores HTTP
- `memory_spike`: Incremento en uso de memoria
- `traffic_drop`: Caída abrupta en tasa de peticiones

### Ciclo de Vida de una Anomalía

```
Normal Traffic
    ↓
Potential anomaly (1/2 ciclos; sin alerta todavía)
    ↓
🚨 NEW ANOMALY DETECTED (alerta enviada a Opsgenie)
    ↓
⏱️ Heartbeat cada 30s (logs informativos; configurable)
    ↓
🔔 Escalation después de 30 min (re-alerta si persiste)
    ↓
✅ RESOLVED (notificación cuando se resuelve)
    ↓
Normal Traffic
```

## ⚙️ Configuración

### Archivos de Configuración

| Archivo | Descripción | Parámetros Clave |
|---------|-------------|------------------|
| `config/model.yaml` | Arquitectura LSTM y rutas | model.paths.base, encoder_layers, dropout: 0.1 |
| `config/windowing.yaml` | Ventanas temporales | window_size: 20 (10 min), stride: 1 para training |
| `config/alerting.yaml` | Alertas y umbrales | percentile: 99.5, min_confidence: 0.25, consecutive_anomaly_cycles: 2 |
| `config/data.yaml` | Prometheus y métricas | inference_minutes: 10, history_hours: 2160 (90 días), sampling_interval: 30s |

### Parámetros de Deduplicación (alerting.yaml)

```yaml
rate_limiting:
  enable_deduplication: true              # Activar deduplicación inteligente
  min_confidence: 0.25                    # 25% sobre threshold para alertar
  consecutive_anomaly_cycles: 2           # Confirmar anomalía en 2 ciclos consecutivos
  heartbeat_interval_seconds: 30          # Heartbeat cada 30 segundos
  escalation_threshold_minutes: 30        # Escalar si persiste 30+ min
  escalation_interval_minutes: 15         # Re-alertar cada 15 min
  send_resolved_notification: true        # Notificar resolución
```

### Métricas Monitoreadas

| Métrica | Descripción | Agregación Prometheus |
|---------|-------------|----------------------|
| `request_rate` | Tasa de peticiones HTTP | SUM across endpoints |
| `latency_p95` | Percentil 95 de latencia | MAX (worst case) |
| `memory_usage` | Uso de memoria del servicio (`job="mock-tv-service"` en dev) | MEAN |
| `error_rate` | Tasa de errores HTTP | SUM across endpoints |
| `cpu_usage` | Uso de CPU (`job="mock-tv-service"` en dev) | SUM |

### Ajuste de Sensibilidad

Para reducir falsos positivos, ajustar en `config/alerting.yaml`:

```yaml
threshold:
  percentile: 99.5        # ↑ más alto = menos sensible
  
rate_limiting:
  min_confidence: 0.25    # ↑ más alto = menos alertas marginales
```

Para aumentar sensibilidad (capturar más anomalías):

```yaml
threshold:
  percentile: 95.0        # ↓ más bajo = más sensible
  
rate_limiting:
  min_confidence: 0.15    # ↓ más bajo = más alertas
```

## 🏗️ Arquitectura del Sistema

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

### Pipeline de Detección

1. **Recolección**: Prometheus scrapes mock service cada 30s
2. **Inferencia**: Detector consulta Prometheus cada 30s (ventana de 10 min)
3. **Readiness guard**:
   - Requiere al menos `window_size` muestras reales
   - Rechaza gaps > `2 × sampling_interval`
   - Rechaza muestras stale > `2 × sampling_interval`
   - Si la ventana no está lista, omite el ciclo (no zero-padding en producción)
4. **Preprocesamiento**: 
   - Normalización con fixed_minmax scaler
   - Feature engineering (6 features temporales)
   - Sliding window (20 timesteps × 30s = 10 min)
5. **Modelo**: LSTM Autoencoder reconstruye secuencia
6. **Detección**: Compara error de reconstrucción vs threshold
7. **Confirmación**: 2 ciclos anomalos consecutivos antes de abrir alerta nueva
8. **Deduplicación**: State machine evita alertas repetidas
9. **Alertas**: Opsgenie + enlaces a Grafana

### Sistema de Deduplicación

**Problema resuelto**: Sin deduplicación, el sistema alertaba cada 30 segundos durante la misma anomalía.

**Solución implementada**:
- UUID único por anomalía
- State tracking (NEW → ONGOING → RESOLVED)
- Filtrado por confianza (25% sobre threshold)
- Confirmación de 2 ciclos consecutivos antes de abrir una alerta
- Heartbeat logs cada 30 segundos
- Escalación automática a los 30 minutos
- Peak error tracking para análisis

**Resultado**: 1 alerta por anomalía (+ resolved notification) vs 12+ alertas sin deduplicación.

## 📚 Documentación

Ver documentación completa para:

- **[Guía de Instalación](docs/installation.md)** - Setup completo paso a paso
- **[Troubleshooting](docs/troubleshooting.md)** - Problemas comunes y soluciones
- **[Diario de Issues](TROUBLESHOOTING_JOURNAL.md)** - Historial de issues documentados con resoluciones

### Issues Destacados (Resueltos)

| Issue | Descripción | Solución |
|-------|-------------|----------|
| #2 | Latency 4x inflada | Agregación incorrecta (SUM → MAX) |
| #8 | Alert fatigue | Sistema de deduplicación completo |
| #9 | Cascading severity alerts | Simplificación de lógica de estado |
| #10 | Zero-padding durante inference | inference_minutes 5→10 min |
| #17+ | Drift mock/sintético, gaps Prometheus | Core compartido, readiness guard, tuning |

## 🐛 Troubleshooting Rápido

### Detector no muestra logs
```bash
# Esto es normal - logs DEBUG solo se muestran si hay anomalías
docker logs tv-anomaly-detector --tail 50

# Verificar que está corriendo
docker-compose ps anomaly-detection  # Debe mostrar "healthy"
```

### Falsos positivos frecuentes
```yaml
# Subir min_confidence en config/alerting.yaml
rate_limiting:
  min_confidence: 0.30  # Era 0.25
```

### Cambios no se aplican
```bash
# Cambios de config montada: restart suele alcanzar
docker-compose --profile dev restart anomaly-detection

# Cambios de código/Dockerfile/dependencias: rebuild
docker-compose --profile dev up -d --build anomaly-detection
```

Ver [docs/troubleshooting.md](docs/troubleshooting.md) para más información.

## 🔬 Testing

### Unit Tests
```bash
pytest tests/unit/
```

### Evaluation Script
Use `--headless` for CI/automation to avoid blocking on plot display:
```bash
python scripts/evaluate_model.py --headless
```

### Integration Tests
```bash
# Levantar entorno de desarrollo
docker-compose --profile dev up -d

# Inyectar anomalía y verificar detección
curl -X POST http://localhost:8000/anomaly \
  -H "Content-Type: application/json" \
  -d '{"type": "latency_spike", "duration": 120}'

# Verificar logs
docker logs tv-anomaly-detector | grep "NEW ANOMALY"
```

## 🎓 Contexto Académico

Este proyecto es parte del **Trabajo Final de la Especialización en Inteligencia Artificial** de la Universidad de Buenos Aires (UBA).

**Objetivo**: Implementar un sistema de detección de anomalías en tiempo real para servicios de streaming de video (TV-over-IP) utilizando técnicas de deep learning, específicamente autoencoders LSTM.

**Resultados Destacados**:
- Threshold tuneado vía normal-error p99.5 (`models/anomaly_threshold.npy`, último valor: ~0.0045638)
- Evaluación offline con precisión/recall/F1 registrados en `evaluation/evaluation_iterations.csv`
- Reducción de 12+ alertas por incidente a 1 alerta + notificación de resolución
- Sistema de deduplicación con confirmación, heartbeat y escalación inteligente

## 📄 Licencia

Este proyecto es trabajo académico de la Especialización en Inteligencia Artificial (UBA).

**Autor**: Ing. Christopher Charaf  
**Institución**: Universidad de Buenos Aires (UBA)  
**Programa**: Especialización en Inteligencia Artificial  
**Cliente**: Kaltura Inc.  
**Año**: 2026

## 🙏 Agradecimientos

- **Kaltura Inc.** por proveer el caso de uso real y contexto de producción
- **Universidad de Buenos Aires** por el programa de especialización
- **Comunidad open source** de TensorFlow, Scikit-learn, y Prometheus
