FROM python:3.10-slim

# Instalar dependencias del sistema
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    && rm -rf /var/lib/apt/lists/*

# Crear usuario no-root
RUN useradd --create-home --shell /bin/bash anomaly_user

WORKDIR /app

# Copiar requirements y instalar dependencias Python
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copiar código fuente
COPY src/ ./src/
COPY mock_service/traffic_simulation_core.py ./mock_service/
COPY config/ ./config/
COPY scripts/ ./scripts/

# Crear directorios necesarios
RUN mkdir -p models/ logs/ && \
    chown -R anomaly_user:anomaly_user /app

# Cambiar a usuario no-root
USER anomaly_user

# Exponer puerto
EXPOSE 8080

# Comando por defecto
CMD ["python", "scripts/inference.py"]
