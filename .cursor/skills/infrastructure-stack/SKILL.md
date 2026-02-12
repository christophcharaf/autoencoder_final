# Infrastructure Stack -- LSTM Autoencoder Anomaly Detection

## Docker Compose Services

```yaml
# Profile: dev (all 4 services)
# Start:  docker-compose --profile dev up -d --build
# Stop:   docker-compose --profile dev down
# Rebuild one: docker-compose build anomaly-detection
```

| Service | Image | Ports | Volumes | Depends on |
|---------|-------|-------|---------|------------|
| mock-service | Built from `mock_service/` | 8000:8000 | -- | -- |
| prometheus | prom/prometheus:latest | 9090:9090 | `./prometheus.yml:/etc/prometheus/prometheus.yml`, `prometheus_data:/prometheus` | mock-service |
| anomaly-detection | Built from `Dockerfile` | — (sin HTTP) | `./models`, `./config`, `./logs` | — |
| grafana | grafana/grafana:latest | 3000:3000 | `./grafana/provisioning`, `./grafana/dashboards` | prometheus |

## Prometheus Configuration

File: `prometheus.yml`

```yaml
global:
  scrape_interval: 30s     # MUST match config/data.yaml sampling_interval
  evaluation_interval: 30s

scrape_configs:
  - job_name: 'mock-tv-service'
    static_configs:
      - targets: ['mock-service:8000']
    scrape_interval: 30s
    scrape_timeout: 10s
```

**Critical alignment rule:** `scrape_interval` in `prometheus.yml` must equal `sampling_interval` in `config/data.yaml`. Both are currently 30s.

**Retention:** 15 days (`--storage.tsdb.retention.time=15d` in docker-compose command)

**Data persistence:** Named volume `prometheus_data` persists data across `docker-compose down`. Only destroyed by `docker volume rm` or `docker-compose down -v`.

## Common Operations

```bash
# Full stack start
docker-compose --profile dev up -d --build

# Stop without losing Prometheus data
docker-compose --profile dev down

# Stop AND delete Prometheus data (destructive)
docker-compose --profile dev down -v

# Run training inside container
docker-compose --profile dev run --rm anomaly-detection python scripts/train.py

# View specific container logs
docker logs tv-anomaly-detector --since 10m --follow

# Check Prometheus targets
curl -s http://localhost:9090/api/v1/targets | python -m json.tool

# Check Prometheus data volume size
docker system df -v | grep prometheus_data
```

## Network Topology

All services on `monitoring` bridge network. Service names resolve as hostnames:
- `mock-service:8000` -- metrics endpoint
- `prometheus:9090` -- query API
- `anomaly-detection` -- polling service (no HTTP, logs only)
- `grafana:3000` -- dashboards

## Port Mapping

| Port | Service | External access |
|------|---------|----------------|
| 8000 | mock-service | http://localhost:8000/metrics |
| 9090 | prometheus | http://localhost:9090 |
| — | anomaly-detection | Servicio polling, sin HTTP expuesto (logs: docker logs tv-anomaly-detector) |
| 3000 | grafana | http://localhost:3000 (admin/admin) |
