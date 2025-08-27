#!/usr/bin/env python3

"""
Script de configuración inicial para el sistema de detección de anomalías
"""

import os
import sys
import subprocess
import shutil
from pathlib import Path

def create_directory_structure():
    """Crea la estructura de directorios del proyecto"""
    print("Creating directory structure...")
    
    directories = [
        "src/data",
        "src/models", 
        "src/alerting",
        "src/utils",
        "config",
        "scripts",
        "models",
        "logs",
        "tests/unit",
        "tests/integration",
        "docs"
    ]
    
    for directory in directories:
        Path(directory).mkdir(parents=True, exist_ok=True)
        
        # Crear __init__.py en directorios de Python
        if directory.startswith("src/"):
            init_file = Path(directory) / "__init__.py"
            init_file.touch()
    
    print("✅ Directory structure created")

def install_python_dependencies():
    """Instala dependencias de Python"""
    print("Installing Python dependencies...")
    
    try:
        subprocess.run([
            sys.executable, "-m", "pip", "install", "-r", "requirements.txt"
        ], check=True)
        print("✅ Python dependencies installed")
    except subprocess.CalledProcessError:
        print("❌ Failed to install Python dependencies")
        return False
    
    return True

def main():
    """Función principal de setup"""
    print("=== Anomaly Detection System Setup ===")
    
    create_directory_structure()
    
    if install_python_dependencies():
        print("\n🎉 Setup completed successfully!")
        print("\nNext steps:")
        print("1. Configure .env file")
        print("2. Train model: python scripts/train.py")
        print("3. Start detection: python scripts/inference.py")
    else:
        print("\n❌ Setup failed")
        sys.exit(1)

if __name__ == "__main__":
    main()
