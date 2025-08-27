.PHONY: help install activate train inference test lint format clean jupyter docker-build docker-run

help: ## 🔍 Mostrar ayuda
	@echo "🚀 TV Anomaly Detection - Mamba Commands"
	@echo "========================================"
	@echo ""
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

install: ## 📦 Setup completo con Mamba
	./setup-mamba.sh

activate: ## 🔄 Activar ambiente (mostrar comando)
	@echo "Run: mamba activate tv-anomaly-detection"

env-info: ## ℹ️  Información del ambiente
	@echo "Environment info:"
	@mamba info --envs | grep tv-anomaly-detection || echo "❌ Environment not found"
	@echo "Active environment: $${CONDA_DEFAULT_ENV:-none}"

update: ## 🔄 Actualizar ambiente
	mamba env update -f environment.yml

train: ## 🧠 Entrenar modelo
	python scripts/train.py

inference: ## 🔍 Ejecutar detección de anomalías
	python scripts/inference.py

jupyter: ## 📓 Abrir Jupyter Lab
	jupyter lab --ip=0.0.0.0 --port=8888 --no-browser

test: ## 🧪 Ejecutar tests
	pytest tests/ -v --cov=src --cov-report=html

test-quick: ## ⚡ Tests rápidos (sin coverage)
	pytest tests/ -v -x

lint: ## 🔍 Linting con flake8
	flake8 src/ tests/ scripts/

format: ## ✨ Formatear código
	black src/ tests/ scripts/
	isort src/ tests/ scripts/

format-check: ## ✅ Verificar formato
	black --check src/ tests/ scripts/
	isort --check-only src/ tests/ scripts/

type-check: ## 🔍 Type checking
	mypy src/

clean: ## 🧹 Limpiar archivos temporales
	rm -rf __pycache__ .pytest_cache .coverage htmlcov .mypy_cache
	find . -name "*.pyc" -delete
	find . -name "*.pyo" -delete
	find . -name "*~" -delete

clean-models: ## 🗑️ Limpiar modelos entrenados
	rm -rf models/*.h5 models/*.joblib models/*.npy

docker-build: ## 🐳 Construir imagen Docker
	docker build -t tv-anomaly-detection .

docker-run: ## 🐳 Ejecutar container
	docker run -it --rm tv-anomaly-detection

docker-dev: ## 🐳 Desarrollo con Docker + servicios
	./scripts/deploy.sh development

benchmark: ## ⚡ Benchmark de velocidad Mamba vs Conda
	@echo "🏁 Package Manager Speed Test"
	@echo "============================="
	@echo ""
	@echo "Testing environment creation speed..."
	@echo ""
	@echo "Mamba (current setup):"
	@time mamba env create -n test-mamba-speed -f environment.yml --dry-run > /dev/null 2>&1
	@echo ""
	@echo "Traditional conda would take 5-10x longer! 🔥"
	@echo ""
	@echo "Mamba advantages:"
	@echo "  ✅ 50x faster dependency resolution"
	@echo "  ✅ Parallel downloads" 
	@echo "  ✅ Better error messages"
	@echo "  ✅ 100% conda compatible"

profile: ## 📊 Profiling de memoria del entrenamiento
	mprof run python scripts/train.py
	mprof plot

deps-graph: ## 📊 Grafo de dependencias
	python -c "
import pkg_resources
import sys

installed = [d for d in pkg_resources.working_set]
installed.sort(key=lambda x: x.project_name)

print('📦 Installed packages:')
for pkg in installed[:10]:  # Top 10
    print(f'  {pkg.project_name}=={pkg.version}')
print(f'  ... and {len(installed)-10} more packages')
"

dev-setup: ## 🛠️ Setup completo para desarrollo
	./setup-mamba.sh
	mamba activate tv-anomaly-detection || true
	cp .env.example .env
	@echo ""
	@echo "✅ Development setup completed!"
	@echo "Next: Edit .env file with your configurations"

all: install format lint test ## 🚀 Setup completo + validación

# Shortcuts comunes
i: install
t: train
r: inference  
j: jupyter
f: format
l: lint

# Help por defecto
.DEFAULT_GOAL := help
