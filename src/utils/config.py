import yaml

import yaml
import os
from typing import Dict, Any
from pathlib import Path

# Ensure prometheus-api-client is installed
try:
    import prometheus_api_client
except ImportError:
    import subprocess
    import sys
    subprocess.check_call([sys.executable, '-m', 'pip', 'install', 'prometheus-api-client'])
    import prometheus_api_client
class Config:
    def __init__(self, config_path: str = None):
        """
        Carga configuración desde archivos YAML y variables de entorno
        """ 
        self.config_path = config_path or "config/"
        self.config = self._load_all_configs()
    
    def _load_all_configs(self) -> Dict[str, Any]:
        """Carga todos los archivos de configuración"""
        configs = {}
        config_dir = Path(self.config_path)
        
        if not config_dir.exists():
            print(f"Warning: Config directory {config_dir} not found")
            return self._get_default_config()
        
        # Cargar archivos YAML
        for config_file in config_dir.glob("*.yaml"):
            with open(config_file, 'r') as f:
                config_name = config_file.stem
                configs[config_name] = yaml.safe_load(f)
        
        # Override con variables de entorno
        configs = self._apply_env_overrides(configs)
        
        return configs
    
    def _apply_env_overrides(self, configs: Dict) -> Dict:
        """Aplica overrides desde variables de entorno"""
        # Prometheus
        if os.getenv('PROMETHEUS_URL'):
            if 'data' not in configs:
                configs['data'] = {}
            configs['data']['prometheus_url'] = os.getenv('PROMETHEUS_URL')
        
        # Opsgenie
        if os.getenv('OPSGENIE_API_KEY'):
            if 'alerting' not in configs:
                configs['alerting'] = {}
            configs['alerting']['opsgenie'] = {'api_key': os.getenv('OPSGENIE_API_KEY')}
        
        return configs
    
    def _get_default_config(self) -> Dict:
        """Configuración por defecto para desarrollo"""
        return {
            'windowing': {
                'window_size': 20,
                'step_size': 30,
                'stride': 20
            },
            'model': {
                'encoder_layers': [64, 32, 16],
                'decoder_layers': [16, 32, 64],
                'batch_size': 32,
                'epochs': 50
            },
            'alerting': {
                'threshold': {'method': 'percentile', 'percentile': 95}
            }
        }
    
    def get(self, key: str, default=None):
        """Obtiene valor de configuración usando dot notation"""
        keys = key.split('.')
        value = self.config
        
        for k in keys:
            if isinstance(value, dict) and k in value:
                value = value[k]
            else:
                return default
        
        return value
