#!/usr/bin/env python3

"""
Setup script optimizado para Mamba
"""

import os
import sys
import subprocess
from pathlib import Path

def print_banner():
    """Banner de bienvenida"""
    print("=" * 60)
    print("🐍 TV ANOMALY DETECTION - PYTHON SETUP")
    print("🔥 Optimized for Mamba")
    print("=" * 60)
    print()

def check_environment():
    """Verifica el ambiente de desarrollo"""
    print("🔍 Checking development environment...")
    
    # Verificar si estamos en ambiente Mamba/conda
    conda_env = os.environ.get('CONDA_DEFAULT_ENV')
    if conda_env == 'tv-anomaly-detection':
        print(f"✅ Running in correct environment: {conda_env}")
    elif conda_env:
        print(f"⚠️  Running in environment: {conda_env}")
        print("   Expected: tv-anomaly-detection")
        print("   Run: mamba activate tv-anomaly-detection")
    else:
        print("⚠️  Not in conda/mamba environment")
        print("   Run: mamba activate tv-anomaly-detection")
    
    # Verificar Python version
    python_version = sys.version_info
    if python_version >= (3, 8):
        print(f"✅ Python version: {python_version.major}.{python_version.minor}.{python_version.micro}")
    else:
        print(f"❌ Python version too old: {python_version.major}.{python_version.minor}")
        return False
    
    return True

def create_directories():
    """Crea estructura de directorios"""
    print("📁 Creating project directories...")
    
    directories = [
        "src/data", "src/models", "src/alerting", "src/utils",
        "config", "scripts", "models", "logs", 
        "tests/unit", "tests/integration", "docs",
        "notebooks"  # Para Jupyter development
    ]
    
    for directory in directories:
        Path(directory).mkdir(parents=True, exist_ok=True)
        
        # Crear __init__.py en directorios Python
        if directory.startswith("src/"):
            init_file = Path(directory) / "__init__.py"
            init_file.touch()
    
    print("✅ Directory structure created")

def verify_critical_packages():
    """Verifica paquetes críticos están instalados"""
    print("🔍 Verifying critical packages...")
    
    critical_packages = [
        ('numpy', 'NumPy'),
        ('pandas', 'Pandas'), 
        ('sklearn', 'Scikit-learn'),
        ('tensorflow', 'TensorFlow'),
        ('requests', 'Requests'),
        ('yaml', 'PyYAML'),
        ('joblib', 'Joblib')
    ]
    
    missing = []
    installed_versions = {}
    
    for import_name, display_name in critical_packages:
        try:
            if import_name == 'sklearn':
                import sklearn
                version = sklearn.__version__
            elif import_name == 'yaml':
                import yaml
                version = getattr(yaml, '__version__', 'unknown')
            else:
                module = __import__(import_name)
                version = getattr(module, '__version__', 'unknown')
            
            print(f"  ✅ {display_name}: {version}")
            installed_versions[import_name] = version
            
        except ImportError:
            print(f"  ❌ {display_name}: Not installed")
            missing.append(display_name)
    
    if missing:
        print(f"\n❌ Missing packages: {missing}")
        print("   Run: mamba env update -f environment.yml")
        return False
    
    # Verificar TensorFlow GPU support
    try:
        import tensorflow as tf
        gpus = tf.config.list_physical_devices('GPU')
        if gpus:
            print(f"  🚀 GPU Support: {len(gpus)} device(s) detected")
        else:
            print("  ℹ️  GPU Support: CPU only (normal for most setups)")
    except Exception:
        pass
    
    return True

def install_pip_only_dependencies():
    """Instala dependencias que solo están disponibles via pip"""
    print("📦 Checking pip-only dependencies...")
    
    pip_deps = [
        'prometheus-api-client'
    ]
    
    missing_pip = []
    
    for dep in pip_deps:
        try:
            __import__(dep.replace('-', '_'))
            print(f"  ✅ {dep}: installed")
        except ImportError:
            missing_pip.append(dep)
    
    if missing_pip:
        print(f"Installing missing pip dependencies: {missing_pip}")
        try:
            subprocess.run([
                sys.executable, "-m", "pip", "install"
            ] + missing_pip, check=True)
            print("  ✅ Pip dependencies installed")
        except subprocess.CalledProcessError:
            print("  ❌ Failed to install pip dependencies")
            return False
    
    return True

def create_jupyter_kernel():
    """Registra kernel de Jupyter para el ambiente"""
    print("📓 Setting up Jupyter kernel...")
    
    try:
        subprocess.run([
            sys.executable, "-m", "ipykernel", "install", 
            "--user", "--name", "tv-anomaly-detection",
            "--display-name", "TV Anomaly Detection"
        ], check=True, capture_output=True)
        print("  ✅ Jupyter kernel registered")
    except subprocess.CalledProcessError:
        print("  ⚠️  Could not register Jupyter kernel (non-critical)")

def create_example_config():
    """Crea archivo .env si no existe"""
    if not Path('.env').exists():
        if Path('.env.example').exists():
            print("📝 Creating .env from template...")
            import shutil
            shutil.copy('.env.example', '.env')
            print("  ✅ .env created from .env.example")
            print("  ⚠️  Edit .env with your configurations")
        else:
            print("  ⚠️  .env.example not found")

def show_next_steps():
    """Muestra próximos pasos"""
    conda_env = os.environ.get('CONDA_DEFAULT_ENV')
    
    print("\n🎉 Python setup completed successfully!")
    print()
    print("📋 Next steps:")
    print()
    
    if conda_env != 'tv-anomaly-detection':
        print("1. Activate environment:")
        print("   mamba activate tv-anomaly-detection")
        print()
    
    print("2. Configure services:")
    print("   nano .env  # Edit with your Prometheus/Opsgenie settings")
    print()
    
    print("3. Train your first model:")
    print("   python scripts/train.py")
    print()
    
    print("4. Start anomaly detection:")
    print("   python scripts/inference.py")  
    print()
    
    print("5. Development with Jupyter:")
    print("   jupyter lab")
    print()
    
    print("📚 Useful development commands:")
    print("   make help           # See all available commands")
    print("   make test          # Run tests")
    print("   make format        # Format code")
    print("   make lint          # Check code quality")
    print()

def main():
    """Función principal"""
    print_banner()
    
    if not check_environment():
        print("\n❌ Environment check failed")
        sys.exit(1)
    
    create_directories()
    
    if not verify_critical_packages():
        print("\n❌ Package verification failed")
        print("   Try: mamba env update -f environment.yml")
        sys.exit(1)
    
    if not install_pip_only_dependencies():
        print("\n⚠️  Some pip dependencies failed to install")
    
    create_jupyter_kernel()
    create_example_config()
    show_next_steps()

if __name__ == "__main__":
    main()
