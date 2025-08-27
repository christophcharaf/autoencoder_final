#!/bin/bash

set -e

echo "🚀 TV Anomaly Detection - Mamba Setup"
echo "======================================"
echo ""

# Colores para output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Funciones helper
print_step() {
    echo -e "${BLUE}[STEP]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Detectar OS
detect_os() {
    if [[ "$OSTYPE" == "linux-gnu"* ]]; then
        OS="Linux"
        ARCH=$(uname -m)
    elif [[ "$OSTYPE" == "darwin"* ]]; then
        OS="MacOSX" 
        ARCH=$(uname -m)
    else
        print_error "Unsupported OS: $OSTYPE"
        exit 1
    fi
}

# Verificar si Mamba está instalado
check_mamba() {
    if command -v mamba &> /dev/null; then
        MAMBA_VERSION=$(mamba --version | grep mamba | cut -d' ' -f2)
        print_success "Mamba found: version $MAMBA_VERSION"
        return 0
    else
        return 1
    fi
}

# Instalar Mambaforge
install_mambaforge() {
    print_step "Installing Mambaforge..."
    
    detect_os
    MAMBAFORGE_URL="https://github.com/conda-forge/miniforge/releases/latest/download/Mambaforge-${OS}-${ARCH}.sh"
    INSTALLER="Mambaforge-${OS}-${ARCH}.sh"
    
    print_step "Downloading from: $MAMBAFORGE_URL"
    curl -L -O "$MAMBAFORGE_URL"
    
    print_step "Installing Mambaforge to $HOME/mambaforge"
    bash "$INSTALLER" -b -p "$HOME/mambaforge"
    rm "$INSTALLER"
    
    # Initialize mamba
    print_step "Initializing Mamba..."
    "$HOME/mambaforge/bin/mamba" init bash
    
    # Try to reload shell config
    if [[ -f "$HOME/.bashrc" ]]; then
        source "$HOME/.bashrc" 2>/dev/null || true
    fi
    if [[ -f "$HOME/.zshrc" ]]; then
        source "$HOME/.zshrc" 2>/dev/null || true
    fi
    
    # Add to current session PATH
    export PATH="$HOME/mambaforge/bin:$PATH"
    
    print_success "Mambaforge installed successfully!"
}

# Verificar archivos necesarios
check_files() {
    print_step "Checking required files..."
    
    if [[ ! -f "environment.yml" ]]; then
        print_error "environment.yml not found!"
        exit 1
    fi
    
    print_success "Required files found"
}

# Crear ambiente conda
create_environment() {
    print_step "Creating Mamba environment..."
    
    # Check if environment already exists
    if mamba env list | grep -q "tv-anomaly-detection"; then
        print_warning "Environment 'tv-anomaly-detection' already exists"
        read -p "Update existing environment? (y/N): " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            print_step "Updating environment..."
            mamba env update -f environment.yml
        else
            print_step "Using existing environment"
        fi
    else
        print_step "Creating new environment (this may take 30-60 seconds)..."
        mamba env create -f environment.yml
    fi
    
    print_success "Environment ready!"
}

# Verificar instalación
verify_installation() {
    print_step "Verifying installation..."
    
    # Activate environment for verification
    eval "$(mamba shell.bash hook)"
    mamba activate tv-anomaly-detection
    
    # Test critical imports
    python -c "
import sys
import numpy as np
import pandas as pd
import sklearn
import tensorflow as tf
import requests
import yaml
import joblib

print('✅ Python:', sys.version.split()[0])
print('✅ NumPy:', np.__version__)
print('✅ Pandas:', pd.__version__)
print('✅ Scikit-learn:', sklearn.__version__)
print('✅ TensorFlow:', tf.__version__)
print('✅ Requests:', requests.__version__)
print('✅ PyYAML: OK')
print('✅ Joblib:', joblib.__version__)

# Test TensorFlow GPU (if available)
gpus = tf.config.list_physical_devices('GPU')
if gpus:
    print(f'✅ GPU Support: {len(gpus)} device(s) found')
else:
    print('ℹ️  GPU Support: CPU only')
" 2>/dev/null
    
    if [[ $? -eq 0 ]]; then
        print_success "All packages verified successfully!"
    else
        print_warning "Some packages failed verification, but environment was created"
    fi
}

# Setup proyecto
setup_project() {
    print_step "Setting up project structure..."
    
    # Activate environment
    eval "$(mamba shell.bash hook)"
    mamba activate tv-anomaly-detection
    
    # Run Python setup script if exists
    if [[ -f "scripts/setup.py" ]]; then
        python scripts/setup.py
    fi
}

# Mostrar información final
show_final_info() {
    echo ""
    echo "🎉 Setup completed successfully!"
    echo ""
    echo "📋 Next steps:"
    echo ""
    echo "1. Activate environment:"
    echo "   ${GREEN}mamba activate tv-anomaly-detection${NC}"
    echo ""
    echo "2. Configure your services:"
    echo "   ${YELLOW}cp .env.example .env${NC}"
    echo "   ${YELLOW}# Edit .env with your Prometheus/Opsgenie settings${NC}"
    echo ""
    echo "3. Train your first model:"
    echo "   ${GREEN}python scripts/train.py${NC}"
    echo ""
    echo "4. Start anomaly detection:"
    echo "   ${GREEN}python scripts/inference.py${NC}"
    echo ""
    echo "5. Development with Jupyter:"
    echo "   ${GREEN}jupyter lab${NC}"
    echo ""
    echo "📚 Useful commands:"
    echo "   ${BLUE}mamba list${NC}                    # List installed packages"
    echo "   ${BLUE}mamba env list${NC}               # List all environments" 
    echo "   ${BLUE}mamba env update -f environment.yml${NC}  # Update environment"
    echo "   ${BLUE}mamba deactivate${NC}             # Deactivate environment"
    echo ""
    echo "🏆 Performance comparison:"
    echo "   Traditional conda: 5-10 minutes"
    echo "   Mamba (you): 30-60 seconds 🔥"
    echo ""
}

# Función principal
main() {
    echo "This script will:"
    echo "1. Install Mambaforge (if not present)" 
    echo "2. Create 'tv-anomaly-detection' environment"
    echo "3. Install all ML dependencies (~50+ packages)"
    echo "4. Verify installation"
    echo ""
    
    # Verificar si Mamba ya está instalado
    if check_mamba; then
        print_success "Mamba already installed, skipping Mambaforge installation"
    else
        read -p "Install Mambaforge? This will install to $HOME/mambaforge (y/N): " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            print_error "Mambaforge installation cancelled"
            exit 1
        fi
        install_mambaforge
    fi
    
    # Verificar archivos y crear ambiente
    check_files
    create_environment
    verify_installation
    setup_project
    show_final_info
}

# Ejecutar main
main
