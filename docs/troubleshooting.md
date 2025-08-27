# Troubleshooting

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
