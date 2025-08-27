import yaml
import os
from typing import Dict, Any
from pathlib import Path

class Config:
    """Gestor de configuración optimizado para Mamba"""
    
    def __init__(self, config_path: str = None):
        self.config_path = config_path or "config/"
        self.config = self._load_all_configs()
    
    def _load_all_configs(self) -> Dict[str, Any]:
        """Carga configuraciones desde YAML y env vars"""
        configs = {}
        config_dir = Path(self.config_path)
        
        if not config_dir.exists():
            print(f"Warning: Config directory {config_dir} not found")
            return self._get_default_config()
        
        # Cargar YAMLs
        for config_file in config_dir.glob("*.yaml"):
            with open(config_file, 'r') as f:
                config_name = config_file.stem
                configs[config_name] = yaml.safe_load(f)
        
        # Override con env vars
        configs = self._apply_env_overrides(configs)
        return configs
    
    def _apply_env_overrides(self, configs: Dict) -> Dict:
        """Aplica overrides desde variables de entorno"""
        env_mappings = {
            'PROMETHEUS_URL': ('data', 'prometheus_url'),
            'OPSGENIE_API_KEY': ('alerting', 'opsgenie', 'api_key'),
            'GRAFANA_URL': ('alerting', 'grafana', 'base_url'),
            'MODEL_WINDOW_SIZE': ('windowing', 'window_size'),
            'MODEL_THRESHOLD_PERCENTILE': ('alerting', 'threshold', 'percentile')
        }
        
        for env_var, config_path in env_mappings.items():
            value = os.getenv(env_var)
            if value:
                self._set_nested_config(configs, config_path, value)
        
        return configs
    
    def _set_nested_config(self, configs: Dict, path: tuple, value: str):
        """Establece valor en configuración anidada"""
        current = configs
        for key in path[:-1]:
            if key not in current:
                current[key] = {}
            current = current[key]
        
        # Convert types
        final_key = path[-1]
        if final_key in ['window_size', 'percentile']:
            current[final_key] = int(value)
        else:
            current[final_key] = value
    
    def _get_default_config(self) -> Dict:
        """Config por defecto para desarrollo rápido"""
        return {
            'windowing': {'window_size': 20, 'step_size': 30, 'stride': 20},
            'model': {'encoder_layers': [64, 32, 16], 'batch_size': 32, 'epochs': 50},
            'alerting': {'threshold': {'method': 'percentile', 'percentile': 95}},
            'data': {'prometheus_url': None}
        }
    
    def get(self, key: str, default=None):
        """Obtiene valor con dot notation (ej: 'windowing.window_size')"""
        keys = key.split('.')
        value = self.config
        
        for k in keys:
            if isinstance(value, dict) and k in value:
                value = value[k]
            else:
                return default
        return value
