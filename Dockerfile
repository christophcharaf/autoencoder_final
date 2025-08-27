# Multi-stage build optimizado para Mamba
FROM mambaorg/micromamba:0.15.3 as base

# Configurar micromamba
ENV MAMBA_ROOT_PREFIX=/opt/conda
ENV PATH=$MAMBA_ROOT_PREFIX/bin:$PATH

# Crear usuario y directorio de trabajo
USER root
RUN mkdir -p /app && chown $MAMBA_USER:$MAMBA_USER /app
WORKDIR /app

# Copiar environment.yml
COPY environment.yml .

# Instalar ambiente con micromamba (súper rápido)
USER $MAMBA_USER
RUN micromamba env create -f environment.yml && \
    micromamba clean --all --yes

# Activar ambiente
ENV PATH=/opt/conda/envs/tv-anomaly-detection/bin:$PATH

# Copiar código fuente  
COPY --chown=$MAMBA_USER:$MAMBA_USER src/ ./src/
COPY --chown=$MAMBA_USER:$MAMBA_USER config/ ./config/
COPY --chown=$MAMBA_USER:$MAMBA_USER scripts/ ./scripts/

# Crear directorios para runtime
RUN mkdir -p models logs

# Exponer puerto
EXPOSE 8080

# Comando por defecto
CMD ["python", "scripts/inference.py"]
