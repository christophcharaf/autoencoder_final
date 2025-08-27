# Guía de Instalación

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
