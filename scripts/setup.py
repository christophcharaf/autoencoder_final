#!/usr/bin/env python3
"""
Setup simple para TV Anomaly Detection
"""

import subprocess
import sys
from pathlib import Path

def run_command(command, description):
    """Ejecuta un comando y muestra resultado"""
    print(f"\n🔧 {description}...")
    try:
        result = subprocess.run(command, shell=True, check=True, capture_output=True, text=True)
        print(f"✅ {description} - OK")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ {description} - FAILED")
        if e.stderr:
            print(f"Error: {e.stderr}")
        return False

def create_requirements_yml():
    """Crea requirements.yml si no existe"""
    req_file = Path("requirements.yml")
    if req_file.exists():
        print("✅ requirements.yml already exists")
        return
    
    print("📝 Creating requirements.yml...")
    content = """name: anomaly-detection
channels:
  - conda-forge
  - defaults
dependencies:
  - python=3.10
  - tensorflow>=2.13.0
  - pandas>=1.5.0
  - numpy>=1.24.0
  - scikit-learn>=1.3.0
  - matplotlib>=3.7.0
  - seaborn>=0.12.0
  - pyyaml>=6.0
  - requests>=2.31.0
  - joblib>=1.3.0
  - pip
  - pip:
    - prometheus-client>=0.17.0
    - python-dotenv>=1.0.0
"""
    req_file.write_text(content)
    print("✅ requirements.yml created")

def main():
    print("=== TV Anomaly Detection Setup ===")
    
    # 1. Crear requirements.yml si no existe
    create_requirements_yml()
    
    # 2. Instalar mamba en base
    if not run_command("conda install mamba -n base -c conda-forge -y", "Installing mamba"):
        print("⚠️ Mamba installation failed, continuing anyway...")
    
    # 3. Crear environment con mamba
    if not run_command("mamba env create -f requirements.yml", "Creating environment with mamba"):
        print("🔄 Trying with conda as fallback...")
        if not run_command("conda env create -f requirements.yml", "Creating environment with conda"):
            print("❌ Environment creation failed")
            sys.exit(1)
    
    print("\n🎉 Setup completed!")
    print("\nNext steps:")
    print("1. conda activate anomaly-detection")
    print("2. python scripts/train.py")

if __name__ == "__main__":
    main()