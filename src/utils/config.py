"""
Configuration loader for the LSTM Autoencoder anomaly detection system.

Loads YAML files from config/ and applies environment variable overrides.
Supports dot-notation access (e.g., config.get('data.prometheus.url')).
"""

import os
import re
import yaml
from pathlib import Path
from typing import Any, Dict


class Config:
    def __init__(self, config_path: str = None):
        """
        Load configuration from YAML files and environment variables.

        Args:
            config_path: Directory containing YAML config files. Defaults to 'config/'.
        """
        self.config_path = config_path or "config/"
        self.config = self._load_all_configs()

    def _load_all_configs(self) -> Dict[str, Any]:
        """Load all YAML configuration files from the config directory."""
        configs = {}
        config_dir = Path(self.config_path)
        
        if not config_dir.exists():
            print(f"Warning: Config directory {config_dir} not found")
            return self._get_default_config()
        
        for config_file in config_dir.glob("*.yaml"):
            with open(config_file, 'r') as f:
                config_name = config_file.stem
                file_content = yaml.safe_load(f)
                # Flatten the nested structure (e.g., {'model': {...}} -> store as 'model')
                if isinstance(file_content, dict) and config_name in file_content:
                    configs[config_name] = file_content[config_name]
                else:
                    configs[config_name] = file_content
        
        # Apply environment variable overrides
        configs = self._apply_env_overrides(configs)
        
        return configs
    
    def _apply_env_overrides(self, configs: Dict) -> Dict:
        """Apply overrides from environment variables and expand ${VAR} placeholders."""
        # First, expand any ${VAR} placeholders in the config values
        configs = self._expand_env_vars(configs)
        
        # Prometheus
        if os.getenv('PROMETHEUS_URL'):
            if 'data' not in configs:
                configs['data'] = {}
            if 'prometheus' not in configs['data']:
                configs['data']['prometheus'] = {}
            configs['data']['prometheus']['url'] = os.getenv('PROMETHEUS_URL')
        
        # Opsgenie
        if os.getenv('OPSGENIE_API_KEY'):
            if 'alerting' not in configs:
                configs['alerting'] = {}
            if 'opsgenie' not in configs['alerting']:
                configs['alerting']['opsgenie'] = {}
            configs['alerting']['opsgenie']['api_key'] = os.getenv('OPSGENIE_API_KEY')
        
        # Grafana
        if os.getenv('GRAFANA_URL'):
            if 'alerting' not in configs:
                configs['alerting'] = {}
            if 'grafana' not in configs['alerting']:
                configs['alerting']['grafana'] = {}
            configs['alerting']['grafana']['base_url'] = os.getenv('GRAFANA_URL')
        
        return configs
    
    def _expand_env_vars(self, obj: Any) -> Any:
        """Recursively expand ${VAR} placeholders with environment variable values"""
        if isinstance(obj, dict):
            return {k: self._expand_env_vars(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [self._expand_env_vars(item) for item in obj]
        elif isinstance(obj, str):
            def replace_var(match):
                var_name = match.group(1)
                return os.getenv(var_name, match.group(0))  # Keep original if not found
            return re.sub(r'\$\{([^}]+)\}', replace_var, obj)
        else:
            return obj
    
    def _get_default_config(self) -> Dict:
        """Default configuration for development when config directory is missing."""
        return {
            'windowing': {
                'window_size': 20,
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
        """
        Get configuration value using dot notation.

        Args:
            key: Dot-separated path (e.g., 'data.prometheus.url').
            default: Value to return if key not found.

        Returns:
            Config value or default.
        """
        keys = key.split('.')
        value = self.config
        
        for k in keys:
            if isinstance(value, dict) and k in value:
                value = value[k]
            else:
                return default
        
        return value
