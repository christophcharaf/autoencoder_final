# Sistema de Detección de Anomalías TV-over-IP

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
