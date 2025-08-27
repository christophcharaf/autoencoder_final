# Sistema de Detección de Anomalías TV-over-IP 🚀

Sistema de detección de anomalías en tiempo real para servicios de TV-over-IP utilizando autoencoder LSTM. **Optimizado para Mamba** para máxima velocidad de instalación.

## 🚀 Setup Súper Rápido (Mamba)

```bash
# 1. Instalar Mambaforge (si no lo tienes)
curl -L -O "https://github.com/conda-forge/miniforge/releases/latest/download/Mambaforge-$(uname)-$(uname -m).sh"
bash Mambaforge-$(uname)-$(uname -m).sh

# 2. Setup automático
./setup-mamba.sh

# 3. Activar y usar
mamba activate tv-anomaly-detection
python scripts/train.py
python scripts/inference.py
```

## ⚡ ¿Por qué Mamba?

- **50x más rápido** que conda tradicional
- **Compatible 100%** con conda (misma sintaxis)
- **Perfecto para ML** (TensorFlow, numpy optimizados)
- **Instalación**: 30-60 segundos vs 5-10 minutos con conda

## 📦 Dependencias Incluidas

✅ **ML Stack**: TensorFlow, NumPy, Pandas, Scikit-learn  
✅ **Data Processing**: Feature engineering temporal, windowing  
✅ **Monitoring**: Prometheus client, alertas Opsgenie  
✅ **Development**: Jupyter Lab, pytest, black, flake8  
✅ **Visualization**: Matplotlib, Seaborn  

## 🎯 Estructura del Proyecto

```
tv-anomaly-detection/
├── src/                    # Código fuente
│   ├── data/              # Prometheus client, preprocessing  
│   ├── models/            # LSTM Autoencoder
│   ├── alerting/          # Opsgenie + Grafana links
│   └── utils/             # Config, logging
├── config/                # YAML configs (modelo, alertas, etc.)
├── scripts/               # train.py, inference.py
├── environment.yml        # Ambiente Mamba/conda
└── setup-mamba.sh        # Setup automático
```

## 🔧 Comandos Principales

```bash
# Gestión de ambiente
mamba activate tv-anomaly-detection
mamba deactivate

# ML Workflow
python scripts/train.py          # Entrenar modelo
python scripts/inference.py      # Detección tiempo real
jupyter lab                      # Desarrollo interactivo

# Testing y Quality
pytest tests/ -v                 # Tests
black src/ --check              # Format check
flake8 src/                     # Linting

# Docker (opcional)
./scripts/deploy.sh development  # Con Prometheus/Grafana
docker-compose up -d             # Solo detector
```

## ⚙️ Configuración

El sistema usa archivos YAML para configuración flexible:

- **`config/model.yaml`**: Arquitectura LSTM, hiperparámetros
- **`config/windowing.yaml`**: Ventanas deslizantes (experimentación en Fase 2)
- **`config/alerting.yaml`**: Opsgenie, Grafana, umbrales
- **`config/data.yaml`**: Métricas Prometheus, feature engineering

## 🎓 Uso Básico

### 1. Entrenamiento
```python
# El modelo aprende patrones normales de tus métricas TV-over-IP
python scripts/train.py

# Salida esperada:
# ✅ Data shape: (20160, 6)
# ✅ Generated 1008 sequences of shape (20, 5)  
# ✅ Model saved to models/lstm_autoencoder.h5
# ✅ Anomaly threshold: 0.1234
```

### 2. Detección en Tiempo Real
```python
# Monitoreo continuo con alertas automáticas
python scripts/inference.py

# Salida esperada:
# 🚀 Starting anomaly detection service...
# Normal operation - reconstruction error: 0.0456
# 🚨 ANOMALY DETECTED: reconstruction error: 0.1456
```

## 📈 Características Avanzadas

### Experimentación con Ventanas (Fase 2)
```yaml
# config/windowing.yaml
experimental:
  enable_overlap: true
  stride_options: [1, 5, 10]  # Ventanas solapadas
```

### Métricas Personalizadas
```yaml
# config/data.yaml  
metrics:
  queries:
    - name: "custom_metric"
      query: "your_prometheus_query"
```

### Desarrollo con Jupyter
```bash
mamba activate tv-anomaly-detection
jupyter lab
# Notebooks automáticamente tienen acceso a todos los módulos
```

## 🐳 Deployment

```bash
# Desarrollo con servicios mock
./scripts/deploy.sh development
# ✅ Prometheus: http://localhost:9090  
# ✅ Grafana: http://localhost:3000

# Producción
./scripts/deploy.sh production
docker logs -f tv-anomaly-detector
```

## 🔍 Troubleshooting

### Instalación lenta
```bash
# Verificar que estás usando Mamba, no conda
which mamba  # Debe mostrar ruta de Mamba
mamba --version  # Verificar versión
```

### Dependencias faltantes  
```bash
mamba list | grep tensorflow  # Verificar TF instalado
mamba env update -f environment.yml  # Actualizar ambiente
```

### GPU no detectada (TensorFlow)
```bash
mamba install tensorflow-gpu  # Si tienes GPU CUDA
python -c "import tensorflow as tf; print(tf.config.list_physical_devices('GPU'))"
```

## 📚 Documentación

- [Instalación detallada](docs/installation.md)
- [Configuración avanzada](docs/configuration.md)
- [API Reference](docs/api.md)
- [Troubleshooting completo](docs/troubleshooting.md)

## 🤝 Contribución

1. Fork el proyecto
2. `mamba env create -f environment.yml`
3. `mamba activate tv-anomaly-detection` 
4. Crear feature branch
5. Commit cambios
6. Push y crear PR

## 📄 Licencia

Proyecto del Trabajo Final - Especialización en Inteligencia Artificial

**Autor**: Ing. Christopher Charaf  
**Cliente**: Kaltura Inc.  
**Tech Stack**: Python + TensorFlow + Mamba 🔥
