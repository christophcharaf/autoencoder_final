import pytest
import os
from src.utils.config import Config

def test_config_default():
    """Test configuración por defecto"""
    config = Config(config_path="nonexistent")
    
    assert config.get('windowing.window_size') == 20
    assert config.get('model.batch_size') == 32

def test_config_get():
    """Test método get con dot notation"""
    config = Config(config_path="nonexistent")
    
    assert config.get('windowing.window_size') == 20
    assert config.get('nonexistent.key', 'default') == 'default'
