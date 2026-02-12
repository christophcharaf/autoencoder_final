# Guía de Resolución de Problemas

## Problemas de Instalación y Docker

### El contenedor no refleja cambios en código o configuración

```bash
# Un simple restart NO es suficiente para aplicar cambios
# Siempre usar el ciclo completo:
docker-compose build anomaly-detection
docker-compose stop anomaly-detection
docker-compose rm -f anomaly-detection
docker-compose up -d anomaly-detection
```

**Explicación:** `docker-compose restart` reutiliza la imagen existente. Los cambios en código fuente, archivos de configuración copiados durante el build, o variables de entorno requieren una reconstrucción completa y recreación del contenedor.

### Error: "Model not found" o archivos de modelo faltantes

```bash
# Verificar que los modelos existen
ls models/
# Esperados: lstm_autoencoder.weights.h5, lstm_autoencoder_config.json,
#            preprocessor.joblib, anomaly_threshold.npy

# Si no existen, entrenar primero
python scripts/train.py

# Reconstruir contenedor para copiar modelos
docker-compose build anomaly-detection
```

### Error: "Prometheus connection failed"

```bash
# Verificar que Prometheus está corriendo
docker-compose ps prometheus

# Probar conectividad desde el host
curl http://localhost:9090/api/v1/status/config

# Verificar la URL configurada en config/data.yaml
# Dentro de Docker, usar: http://prometheus:9090
# Desde el host, usar: http://localhost:9090
```

**Nota:** El detector se conecta a Prometheus usando el nombre del servicio Docker (`prometheus:9090`), no `localhost`. Si Prometheus requiere autenticación, configurar `PROMETHEUS_TOKEN` en `.env`.

### Variables de entorno no se aplican

Las variables de entorno definidas en `docker-compose.yml` solo se aplican al **crear** el contenedor. Un `restart` no las actualiza.

```bash
# Después de cambiar variables en docker-compose.yml:
docker-compose stop anomaly-detection
docker-compose rm -f anomaly-detection
docker-compose up -d anomaly-detection
```

---

## Problemas de Detección

### Alta tasa de falsos positivos

**Causa más común:** Discrepancia entre datos de entrenamiento (sintéticos) y datos reales de Prometheus.

**Solución inmediata** - Ajustar el margen de confianza:

```yaml
# config/alerting.yaml
rate_limiting:
  min_confidence: 0.25    # Subir para filtrar detecciones marginales
                           # Umbral efectivo = threshold × (1 + min_confidence)
```

**Solución a largo plazo** - Reentrenar con datos reales:

```bash
# Verificar cuánto historial tiene Prometheus (necesita ~7 días)
# Luego reentrenar:
python scripts/train.py

# Reconstruir y reiniciar
docker-compose build anomaly-detection
docker-compose stop anomaly-detection && docker-compose rm -f anomaly-detection
docker-compose up -d anomaly-detection
```

**Solución alternativa** - Subir el percentil del umbral:

```yaml
# config/alerting.yaml
threshold:
  percentile: 99.5    # Más alto = menos falsos positivos (default: 99.5)
```

Requiere reentrenamiento después de cambiar este valor.

### El detector no muestra logs de actividad

Los logs de operación normal se emiten a nivel `DEBUG`, que no se muestra por defecto. Esto es comportamiento esperado cuando no hay anomalías.

```bash
# Ver todos los logs (incluyendo DEBUG)
docker logs tv-anomaly-detector --tail 50

# Si solo se ven logs de inicialización y nada más,
# el detector está funcionando correctamente y filtrando
# detecciones de baja confianza.
```

**Verificar que el detector está activo:**

```bash
docker-compose ps anomaly-detection
# Debe mostrar "healthy" en STATUS
```

### Valores de métricas inflados (especialmente latencia)

**Causa:** Las queries PromQL pueden devolver múltiples series temporales (una por endpoint), y si se agregan incorrectamente (e.g., sumando latencias en vez de tomar el máximo), los valores se inflan.

**Verificación:**

```bash
# Comparar valor en Grafana vs logs del detector
docker logs tv-anomaly-detector --tail 20
# Buscar la línea "Current Metrics" y comparar con el dashboard de Grafana
```

**Solución:** El código en `src/data/prometheus_client.py` utiliza diferentes métodos de agregación por métrica:

| Métrica | Agregación | Razón |
|---------|------------|-------|
| `request_rate` | `sum` | Sumar tasas de todos los endpoints |
| `latency_p95` | `max` | Peor caso de latencia entre endpoints |
| `memory_usage` | `mean` | Promedio de uso de memoria |
| `error_rate` | `sum` | Sumar errores de todos los endpoints |
| `cpu_usage` | `sum` | Sumar uso de CPU |

### Anomalía detectada en tráfico normal (error de reconstrucción ~1.0)

Si el error de reconstrucción en tráfico normal ronda ~1.0 y el umbral es ~0.93, el modelo fue entrenado con datos sintéticos que no coinciden exactamente con los patrones reales.

```bash
# Verificar el error de reconstrucción en operación normal
docker logs tv-anomaly-detector --tail 10
# Buscar: "Normal - error: X.XXXX (threshold: Y.YYYY)"
```

**Solución:** Reentrenar con datos reales una vez que Prometheus tenga suficiente historial (7+ días).

---

## Sistema de Deduplicación de Alertas

### Cómo funciona el ciclo de vida de una anomalía

```
Normal → [Detección] → NEW ANOMALY → [Cada 3 min] → Heartbeat
                                    → [30+ min]    → Escalation
                                    → [Se resuelve] → RESOLVED → Normal
```

1. **NEW ANOMALY**: Primera detección. Se asigna un UUID y se envía alerta completa.
2. **Heartbeat** (cada 3 min): Log informativo con error actual, inicial y pico.
3. **Escalation** (30+ min): Re-alerta a Opsgenie si la anomalía persiste.
4. **RESOLVED**: Notificación cuando el error baja del umbral efectivo.

### Logs esperados durante una anomalía

```
# Detección inicial
🚨 NEW ANOMALY DETECTED
📊 Current Metrics:
   request_rate: 26.80
   latency_p95: 8.494s      ← Valor anómalo
   ...
🚨 ANOMALY DETECTED:
   Reconstruction error: 4.7030
   Threshold: 0.9254
   Confidence: 4.08

# Heartbeat (cada 3 minutos)
⏱️ Anomaly ongoing for 3m 0s
   Current error: 15.4364 (initial: 2.3949, peak: 15.4364)
   Anomaly ID: dea4ac2f-088c-4762-a4c5-9d3818e8098e

# Resolución
✅ RESOLVED: Anomaly cleared after 15m 30s
   Anomaly ID: dea4ac2f-088c-4762-a4c5-9d3818e8098e
   Initial error: 2.3949, Peak: 22.5369
```

### El detector alerta repetidamente por la misma anomalía

Verificar que la deduplicación está habilitada:

```yaml
# config/alerting.yaml
rate_limiting:
  enable_deduplication: true
```

Si sigue alertando repetidamente, asegurarse de haber reconstruido el contenedor después de cambiar la configuración.

### Anomalía se resuelve y re-detecta inmediatamente

**Causa:** El error de reconstrucción en tráfico normal está justo por debajo del umbral efectivo. Al fluctuar ligeramente, cruza el umbral de nuevo.

**Solución:** Subir `min_confidence`:

```yaml
rate_limiting:
  min_confidence: 0.25    # Subir si hay detecciones intermitentes
```

El umbral efectivo se calcula como: `threshold × (1 + min_confidence)`.
Con threshold 0.9254 y min_confidence 0.25, el umbral efectivo es **1.1568**.

---

## Grafana

### Los enlaces de Grafana no funcionan

**Síntoma:** Las URLs generadas en los logs o alertas no cargan el dashboard.

**Verificar la configuración:**

```yaml
# config/alerting.yaml
grafana:
  base_url: "${GRAFANA_URL}"            # Se resuelve desde variable de entorno
  dashboard_uid: "tv-metrics-dashboard"  # Debe coincidir con el UID del dashboard
```

```yaml
# docker-compose.yml
environment:
  - GRAFANA_URL=http://localhost:3000    # Para acceso desde el navegador
```

**Causas comunes:**
1. `GRAFANA_URL` configurado como `http://grafana:3000` (hostname interno de Docker, no accesible desde el navegador). Usar `http://localhost:3000` para desarrollo.
2. `dashboard_uid` no coincide con el UID real del dashboard en Grafana.
3. Cambio de variable de entorno sin recrear el contenedor.

**Verificar UID del dashboard:**
- Abrir Grafana (`http://localhost:3000`)
- Navegar al dashboard de TV Metrics
- El UID aparece en la URL: `http://localhost:3000/d/<UID>/...`

### Dashboard no muestra datos

```bash
# Verificar que Prometheus tiene datos
curl "http://localhost:9090/api/v1/query?query=up"

# Verificar que el mock service está generando métricas
curl http://localhost:8000/metrics | head -20

# Verificar el datasource en Grafana
# Settings → Data Sources → Prometheus → URL debe ser http://prometheus:9090
```

---

## Inyección de Anomalías (Mock Service)

### Comandos de inyección

```bash
# Inyectar pico de latencia (120 segundos)
curl -X POST http://localhost:8000/anomaly \
  -H "Content-Type: application/json" \
  -d '{"type": "latency_spike", "duration": 120}'

# Inyectar ráfaga de errores
curl -X POST http://localhost:8000/anomaly \
  -H "Content-Type: application/json" \
  -d '{"type": "error_burst", "duration": 120}'

# Inyectar pico de memoria
curl -X POST http://localhost:8000/anomaly \
  -H "Content-Type: application/json" \
  -d '{"type": "memory_spike", "duration": 120}'

# Inyectar caída de tráfico
curl -X POST http://localhost:8000/anomaly \
  -H "Content-Type: application/json" \
  -d '{"type": "traffic_drop", "duration": 120}'

# Verificar anomalías activas
curl http://localhost:8000/anomaly

# Limpiar todas las anomalías
curl -X POST http://localhost:8000/anomaly/clear
```

### Error 415 "Unsupported Media Type"

Incluir el header `Content-Type: application/json` en la petición:

```bash
# Incorrecto (sin header)
curl -X POST http://localhost:8000/anomaly -d '{"type": "latency_spike"}'

# Correcto (con header)
curl -X POST http://localhost:8000/anomaly \
  -H "Content-Type: application/json" \
  -d '{"type": "latency_spike", "duration": 120}'
```

### La anomalía fue inyectada pero el detector no la reporta

1. **Ventana de datos:** El detector usa una ventana de 10 minutos. La anomalía puede tardar 1-2 ciclos (30-60 segundos) en aparecer.
2. **Confianza insuficiente:** Si la anomalía es leve, el confidence puede estar por debajo del `min_confidence`. Verificar en los logs de DEBUG.
3. **Métrica no monitoreada:** Verificar que el tipo de anomalía afecta una de las 5 métricas monitoreadas (`request_rate`, `latency_p95`, `memory_usage`, `error_rate`, `cpu_usage`).

---

## Logs

```bash
# Ver logs del detector en tiempo real
docker logs -f tv-anomaly-detector

# Ver últimas 50 líneas
docker logs tv-anomaly-detector --tail 50

# Filtrar solo alertas y resoluciones
docker logs tv-anomaly-detector 2>&1 | grep -E "(NEW ANOMALY|RESOLVED|ESCALATION|Anomaly ongoing)"

# Ver logs de todos los servicios
docker-compose logs -f
```

---

## Referencia Rápida

### Estructura de archivos del proyecto

```
autoencoder_final/
├── config/                  # Configuración YAML
│   ├── alerting.yaml        # Umbrales, Opsgenie, Grafana, deduplicación
│   ├── data.yaml            # Prometheus, métricas, ventana de datos
│   ├── model.yaml           # Arquitectura LSTM, hiperparámetros
│   └── windowing.yaml       # Ventana deslizante
├── docker-compose.yml       # Servicios Docker
├── Dockerfile               # Imagen del detector
├── grafana/                 # Dashboards y provisioning de Grafana
├── mock_service/            # Servicio simulado de TV-over-IP
├── models/                  # Modelos entrenados (generados)
├── scripts/
│   ├── train.py             # Entrenamiento del modelo
│   ├── inference.py         # Servicio de detección en tiempo real
│   └── evaluate_model.py    # Evaluación del modelo
├── src/
│   ├── alerting/            # Detector, Opsgenie, enlaces Grafana
│   ├── data/                # Cliente Prometheus, preprocesador, windowing
│   ├── models/              # Definición del LSTM Autoencoder
│   └── utils/               # Configuración, logging
└── TROUBLESHOOTING_JOURNAL.md  # Diario cronológico de problemas y soluciones
```
