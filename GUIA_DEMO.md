# Guía de Demostración — Sistema de Detección de Anomalías TV-over-IP

**Documento de referencia rápida para la presentación ante el tutor.**  
Sistema basado en LSTM Autoencoder para detección de anomalías en tiempo real en servicios de streaming de video.

---

## ¿Qué hace el sistema?

El sistema recolecta métricas de TV-over-IP desde Prometheus, las procesa con un autoencoder LSTM, y detecta anomalías (picos de latencia, ráfagas de errores, caídas de tráfico, etc.). Cuando detecta una anomalía, envía alertas a Opsgenie y genera enlaces a dashboards de Grafana para análisis contextual.

**Características principales:**
- Detección en tiempo real cada 30 segundos
- Deduplicación de alertas (1 alerta por incidente en lugar de múltiples)
- Escalación automática tras 30 minutos si la anomalía persiste
- Notificación cuando la anomalía se resuelve

---

## Diagrama del sistema

```
┌─────────────────┐     ┌──────────────┐     ┌─────────────────────┐
│  Mock Service   │────▶│  Prometheus  │────▶│  Detector Anomalías │
│  (Flask :8000)  │     │  (Scraping   │     │  (LSTM Autoencoder) │
│  Métricas +     │     │   :9090)     │     │  :8080              │
│  Inyección      │     └──────┬───────┘     └──────────┬──────────┘
└─────────────────┘            │                        │
                               │                 ┌──────▼──────┐
                        ┌──────▼──────┐          │  Opsgenie   │
                        │   Grafana   │          │  (Alertas)  │
                        │   :3000     │          └─────────────┘
                        └─────────────┘
```

### Flujo del pipeline de detección

```
Prometheus (scrapes cada 30s)
        │
        ▼
Recolección de métricas (request_rate, latency_p95, error_rate, etc.)
        │
        ▼
Preprocesamiento (normalización + feature engineering temporal)
        │
        ▼
Ventana deslizante (20 timesteps ≈ 10 min)
        │
        ▼
LSTM Autoencoder → Error de reconstrucción
        │
        ▼
Comparación vs umbral → ¿Anomalía? → Deduplicación → Alerta Opsgenie
```

---

## Pasos para probar el flujo completo

### 1. Levantar el entorno de desarrollo

```bash
# Clonar y entrar al proyecto
cd autoencoder_final

# Configurar variables (opcional para demo local)
cp .env.example .env

# Levantar servicios: mock, Prometheus, Grafana, detector
docker-compose --profile dev up -d

# Esperar ~30 segundos a que Prometheus recolecte datos
```

### 2. Entrenar el modelo

```bash
# Entrenar con datos de Prometheus (o sintéticos si no hay suficientes)
python scripts/train.py

# Verificar que se generaron los artefactos
ls models/
# Debe incluir: lstm_autoencoder.weights.h5, preprocessor.joblib, anomaly_threshold.npy
```

### 3. Reconstruir y arrancar el detector

```bash
docker-compose build anomaly-detection
docker-compose stop anomaly-detection && docker-compose rm -f anomaly-detection
docker-compose up -d anomaly-detection
```

### 4. Inyectar una anomalía de prueba

```bash
# Pico de latencia (dura ~2 minutos)
curl -X POST http://localhost:8000/anomaly \
  -H "Content-Type: application/json" \
  -d '{"type": "latency_spike", "duration": 120}'

# O ráfaga de errores
curl -X POST http://localhost:8000/anomaly \
  -H "Content-Type: application/json" \
  -d '{"type": "error_burst", "duration": 120}'
```

### 5. Verificar la detección

```bash
# Ver logs del detector (esperar ~2–3 minutos para que la ventana se llene)
docker logs -f tv-anomaly-detector

# O filtrar solo las alertas
docker logs tv-anomaly-detector 2>&1 | grep -E "(NEW ANOMALY|RESOLVED|ESCALATION)"
```

### 6. Explorar dashboards (opcional)

- **Prometheus**: http://localhost:9090  
- **Grafana**: http://localhost:3000 (admin/admin) — dashboard "TV-over-IP Metrics"  
- **Mock Service**: http://localhost:8000  

---

## Comandos frecuentes

### Entrenamiento y evaluación

| Comando | Descripción |
|---------|-------------|
| `python scripts/train.py` | Entrena el modelo con datos de Prometheus o sintéticos |
| `python scripts/evaluate_model.py` | Evalúa el modelo de forma interactiva (muestra ventana gráfica) |
| `python scripts/evaluate_model.py --headless` | Evaluación sin ventana gráfica (útil para CI) |

### Docker y servicios

| Comando | Descripción |
|---------|-------------|
| `docker-compose --profile dev up -d` | Levanta entorno completo (mock, Prometheus, Grafana, detector) |
| `docker-compose up -d anomaly-detection` | Solo el detector (requiere Prometheus externo) |
| `docker-compose build anomaly-detection` | Reconstruir imagen del detector tras cambios |
| `docker-compose stop anomaly-detection && docker-compose rm -f anomaly-detection` | Detener y eliminar contenedor |
| `docker-compose ps` | Estado de los servicios |

### Logs del detector

| Comando | Descripción |
|---------|-------------|
| `docker logs -f tv-anomaly-detector` | Seguir logs en tiempo real |
| `docker logs tv-anomaly-detector --tail 50` | Últimas 50 líneas |
| `docker logs tv-anomaly-detector` + `grep` (ver paso 5) | Filtrar solo alertas importantes |

### Inyección de anomalías (testing)

| Comando | Descripción |
|---------|-------------|
| `curl -X POST http://localhost:8000/anomaly -H "Content-Type: application/json" -d '{"type": "latency_spike", "duration": 120}'` | Pico de latencia |
| `curl -X POST http://localhost:8000/anomaly -H "Content-Type: application/json" -d '{"type": "error_burst", "duration": 120}'` | Ráfaga de errores |
| `curl http://localhost:8000/anomaly` | Ver anomalías activas |
| `curl -X POST http://localhost:8000/anomaly/clear` | Limpiar anomalías inyectadas |

**Tipos disponibles:** `latency_spike`, `error_burst`, `memory_spike`, `traffic_drop`

### Tests unitarios

| Comando | Descripción |
|---------|-------------|
| `pytest tests/unit/` | Ejecutar tests unitarios |

---

## Contexto académico

- **Proyecto**: Trabajo Final — Especialización en IA (UBA)  
- **Objetivo**: Detección de anomalías en tiempo real para TV-over-IP con LSTM Autoencoder  
- **Resultados**: >99.5% tráfico normal sin falsos positivos; detección con >95% confianza; 1 alerta por incidente gracias a deduplicación  

**Documentación adicional:**  
- [README principal](README.md) — Visión general y configuración  
- [docs/installation.md](docs/installation.md) — Instalación detallada  
- [docs/troubleshooting.md](docs/troubleshooting.md) — Problemas frecuentes  
