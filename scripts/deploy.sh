#!/bin/bash

set -e

echo "=== Anomaly Detection System Deployment Script ==="

ENVIRONMENT=${1:-"development"}
echo "Environment: $ENVIRONMENT"

# Verificar dependencias
if ! command -v docker &> /dev/null; then
    echo "❌ Docker is not installed"
    exit 1
fi

if ! command -v docker-compose &> /dev/null; then
    echo "❌ Docker Compose is not installed"  
    exit 1
fi

# Crear .env si no existe
if [[ ! -f .env ]]; then
    cp .env.example .env
    echo "📝 Created .env file - please configure your settings"
fi

# Construir y deployar
echo "Building and deploying..."
docker-compose down

if [[ "$ENVIRONMENT" == "development" ]]; then
    docker-compose --profile dev up -d
else
    docker-compose up -d anomaly-detection
fi

echo "✅ Deployment completed!"
echo "View logs: docker logs -f tv-anomaly-detector"
