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
🚀 **Heartbeat logs** cada 3 minutos para anomalías en curso  
🚀 **Escalación automática** después de 30 minutos de persistencia  
🚀 **Notificaciones de resolución** cuando anomalías se resuelven  
🚀 **Filtrado por confianza** (25% sobre threshold para reducir falsos positivos)  
🚀 **Peak error tracking** para análisis post-incidente  
🚀 **Mock service** para desarrollo y testing  
🚀 **Alineación de ventanas** (inference_minutes = window_size para evitar zero-padding)  

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

# 3. Levantar todos los servicios
docker-compose --profile dev up -d

# 4. Entrenar el modelo
python scripts/train.py

# 5. Reconstruir y reiniciar el detector
docker-compose build anomaly-detection
docker-compose stop anomaly-detection && docker-compose rm -f anomaly-detection
docker-compose up -d anomaly-detection

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
# Ajustar config/data.yaml con URL de Prometheus de producción
docker-compose up -d anomaly-detection
```

## 📁 Estructura del Proyecto

```
autoencoder_final/
├── src/                          # Código fuente
│   ├── data/                     # Pipeline de datos
│   │   ├── prometheus_client.py  # Cliente Prometheus con agregación
│   │   ├── preprocessor.py       # Feature engineering y normalización
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
│   └── evaluate_model.py         # Evaluación y métricas
├── mock_service/                 # Servicio simulado para dev
│   ├── app.py                    # Flask app con métricas
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

# Evaluar modelo (genera evaluation/model_evaluation.png)
python scripts/evaluate_model.py           # Interactivo (muestra ventana)
python scripts/evaluate_model.py --headless  # Use --headless para CI/automación
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
🚨 NEW ANOMALY DETECTED (alerta enviada a Opsgenie)
    ↓
⏱️ Heartbeat cada 3 minutos (logs informativos)
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
| `config/windowing.yaml` | Ventanas temporales | window_size: 20 (10 min), stride: 20 |
| `config/alerting.yaml` | Alertas y umbrales | percentile: 99.5, min_confidence: 0.25 |
| `config/data.yaml` | Prometheus y métricas | inference_minutes: 10, history_hours: 168 |

### Parámetros de Deduplicación (alerting.yaml)

```yaml
rate_limiting:
  enable_deduplication: true              # Activar deduplicación inteligente
  min_confidence: 0.25                    # 25% sobre threshold para alertar
  heartbeat_interval_seconds: 180         # Heartbeat cada 3 minutos
  escalation_threshold_minutes: 30        # Escalar si persiste 30+ min
  escalation_interval_minutes: 15         # Re-alertar cada 15 min
  send_resolved_notification: true        # Notificar resolución
```

### Métricas Monitoreadas

| Métrica | Descripción | Agregación Prometheus |
|---------|-------------|----------------------|
| `request_rate` | Tasa de peticiones HTTP | SUM across endpoints |
| `latency_p95` | Percentil 95 de latencia | MAX (worst case) |
| `memory_usage` | Uso de memoria del servicio | MEAN |
| `error_rate` | Tasa de errores HTTP | SUM across endpoints |
| `cpu_usage` | Uso de CPU | SUM |

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
3. **Preprocesamiento**: 
   - Normalización con fixed_minmax scaler
   - Feature engineering (6 features temporales)
   - Sliding window (20 timesteps × 30s = 10 min)
4. **Modelo**: LSTM Autoencoder reconstruye secuencia
5. **Detección**: Compara error de reconstrucción vs threshold
6. **Deduplicación**: State machine evita alertas repetidas
7. **Alertas**: Opsgenie + enlaces a Grafana

### Sistema de Deduplicación

**Problema resuelto**: Sin deduplicación, el sistema alertaba cada 30 segundos durante la misma anomalía.

**Solución implementada**:
- UUID único por anomalía
- State tracking (NEW → ONGOING → RESOLVED)
- Filtrado por confianza (25% sobre threshold)
- Heartbeat logs cada 3 minutos
- Escalación automática a los 30 minutos
- Peak error tracking para análisis

**Resultado**: 1 alerta por anomalía (+ resolved notification) vs 12+ alertas sin deduplicación.

## 📚 Documentación

Ver documentación completa para:

- **[Guía de Instalación](docs/installation.md)** - Setup completo paso a paso
- **[Troubleshooting](docs/troubleshooting.md)** - Problemas comunes y soluciones
- **[Diario de Issues](TROUBLESHOOTING_JOURNAL.md)** - 15 issues documentados con resoluciones

### Issues Destacados (Resueltos)

| Issue | Descripción | Solución |
|-------|-------------|----------|
| #2 | Latency 4x inflada | Agregación incorrecta (SUM → MAX) |
| #8 | Alert fatigue | Sistema de deduplicación completo |
| #9 | Cascading severity alerts | Simplificación de lógica de estado |
| #10 | Zero-padding durante inference | inference_minutes 5→10 min |

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
# Siempre usar ciclo completo (restart NO es suficiente)
docker-compose build anomaly-detection
docker-compose stop anomaly-detection && docker-compose rm -f anomaly-detection
docker-compose up -d anomaly-detection
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
- 99.5% de tráfico normal sin falsos positivos
- Detección de anomalías con >95% de confianza
- Reducción de 12+ alertas por incidente a 1 alerta + notificación de resolución
- Sistema de deduplicación con escalación inteligente

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
