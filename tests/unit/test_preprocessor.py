import pytest
import pandas as pd
import numpy as np
from src.data.preprocessor import DataPreprocessor

def test_temporal_features():
    """Test feature engineering temporal"""
    # Datos de prueba
    data = {
        'timestamp': pd.date_range('2023-01-01', periods=24, freq='H'),
        'value': np.random.randn(24)
    }
    df = pd.DataFrame(data)
    
    preprocessor = DataPreprocessor()
    result = preprocessor._add_temporal_features(df)
    
    # Verificar que se agregaron features temporales
    assert 'hour_sin' in result.columns
    assert 'hour_cos' in result.columns
    assert 'is_weekend' in result.columns
