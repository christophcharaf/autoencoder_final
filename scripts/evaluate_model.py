#!/usr/bin/env python3

"""
Script de evaluación del modelo entrenado
"""

import os
import sys
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from sklearn.metrics import classification_report, confusion_matrix
from datetime import datetime, timedelta

# Agregar src al path
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'src'))

from utils.config import Config
from utils.logging import setup_logger
from data.preprocessor import DataPreprocessor
from data.windowing import WindowGenerator
from models.lstm_autoencoder import LSTMAutoencoder

def generate_test_data_with_anomalies():
    """
    Genera datos de prueba que incluyen anomalías conocidas
    """
    logger = setup_logger()
    logger.info("Generando datos de prueba con anomalías...")
    
    # Datos normales (similar al entrenamiento)
    start_time = datetime.now() - timedelta(hours=24)
    timestamps = pd.date_range(start=start_time, periods=2880, freq='30s')  # 24 horas
    
    np.random.seed(123)  # Diferente seed para test
    n_points = len(timestamps)
    
    # Patrón base normal
    hours = np.array([ts.hour for ts in timestamps])
    daily_pattern = 0.5 + 0.3 * np.sin(2 * np.pi * hours / 24)
    
    data = {
        'timestamp': timestamps,
        'request_rate': daily_pattern * 1000 + np.random.normal(0, 50, n_points),
        'latency_p95': daily_pattern * 200 + 100 + np.random.normal(0, 20, n_points),
        'memory_usage': daily_pattern * 0.7 + 0.3 + np.random.normal(0, 0.05, n_points),
        'error_rate': np.random.exponential(0.01, n_points),
        'cpu_usage': daily_pattern * 0.8 + 0.2 + np.random.normal(0, 0.1, n_points)
    }
    
    # Inyectar anomalías conocidas
    anomaly_indices = []
    
    # Anomalía tipo 1: Pico de latencia (10:00-10:30)
    start_anomaly1 = 10 * 120  # 10:00 AM (120 puntos por hora)
    end_anomaly1 = start_anomaly1 + 60  # 30 minutos
    data['latency_p95'][start_anomaly1:end_anomaly1] *= 3  # Triple latencia
    anomaly_indices.extend(range(start_anomaly1, end_anomaly1))
    
    # Anomalía tipo 2: Caída de request rate (15:00-15:15)  
    start_anomaly2 = 15 * 120
    end_anomaly2 = start_anomaly2 + 30  # 15 minutos
    data['request_rate'][start_anomaly2:end_anomaly2] *= 0.1  # Caída del 90%
    anomaly_indices.extend(range(start_anomaly2, end_anomaly2))
    
    # Anomalía tipo 3: Memory leak (20:00-21:00)
    start_anomaly3 = 20 * 120
    end_anomaly3 = start_anomaly3 + 120  # 1 hora
    leak_pattern = np.linspace(0, 0.4, end_anomaly3 - start_anomaly3)
    data['memory_usage'][start_anomaly3:end_anomaly3] += leak_pattern
    anomaly_indices.extend(range(start_anomaly3, end_anomaly3))
    
    # Crear labels de ground truth
    labels = np.zeros(n_points)
    labels[anomaly_indices] = 1  # 1 = anomalía, 0 = normal
    
    # Asegurar valores válidos
    for col in ['request_rate', 'latency_p95', 'error_rate']:
        data[col] = np.maximum(data[col], 0)
    
    data['memory_usage'] = np.clip(data['memory_usage'], 0, 1)
    data['cpu_usage'] = np.clip(data['cpu_usage'], 0, 1)
    
    df = pd.DataFrame(data)
    return df, labels

def evaluate_model():
    """
    Evalúa el modelo entrenado con datos de prueba
    """
    logger = setup_logger()
    logger.info("=== Evaluando modelo entrenado ===")
    
    config = Config()
    
    # 1. Generar datos de prueba con anomalías conocidas
    df_test, true_labels = generate_test_data_with_anomalies()
    logger.info(f"Datos de prueba generados: {df_test.shape}")
    logger.info(f"Anomalías reales: {np.sum(true_labels)} de {len(true_labels)} ({100*np.sum(true_labels)/len(true_labels):.1f}%)")
    
    # 2. Cargar preprocessor
    preprocessor = DataPreprocessor()
    preprocessor.load_scaler('models/preprocessor.joblib')
    df_processed = preprocessor.transform(df_test)
    
    # 3. Crear ventanas
    window_size = config.get('windowing.window_size', 20)
    stride = config.get('windowing.stride', 20)
    
    windower = WindowGenerator(window_size=window_size, stride=stride)
    X_test, _ = windower.create_sequences(df_processed)
    
    # Ajustar labels para ventanas
    n_windows = len(X_test)
    window_labels = []
    for i in range(n_windows):
        start_idx = i * stride
        end_idx = start_idx + window_size
        # Una ventana es anómala si contiene al menos 1 anomalía
        window_has_anomaly = np.any(true_labels[start_idx:end_idx])
        window_labels.append(int(window_has_anomaly))
    
    y_true = np.array(window_labels)
    logger.info(f"Ventanas de prueba: {len(X_test)}")
    logger.info(f"Ventanas anómalas: {np.sum(y_true)} de {len(y_true)} ({100*np.sum(y_true)/len(y_true):.1f}%)")
    
    # 4. Cargar modelo y threshold
    input_shape = (X_test.shape[1], X_test.shape[2])
    model = LSTMAutoencoder(input_shape=input_shape)
    model.load('models/lstm_autoencoder.h5')
    
    threshold = np.load('models/anomaly_threshold.npy')
    logger.info(f"Threshold de anomalías: {threshold:.4f}")
    
    # 5. Calcular errores de reconstrucción
    reconstruction_errors = model.compute_reconstruction_error(X_test)
    logger.info(f"Error de reconstrucción - Mean: {reconstruction_errors.mean():.4f}, Std: {reconstruction_errors.std():.4f}")
    logger.info(f"Error de reconstrucción - Min: {reconstruction_errors.min():.4f}, Max: {reconstruction_errors.max():.4f}")
    
    # 6. Clasificar anomalías
    y_pred = (reconstruction_errors > threshold).astype(int)
    
    # 7. Calcular métricas
    from sklearn.metrics import precision_score, recall_score, f1_score, accuracy_score
    
    precision = precision_score(y_true, y_pred, zero_division=0)
    recall = recall_score(y_true, y_pred, zero_division=0)
    f1 = f1_score(y_true, y_pred, zero_division=0)
    accuracy = accuracy_score(y_true, y_pred)
    
    logger.info("=== RESULTADOS DE EVALUACIÓN ===")
    logger.info(f"Accuracy:  {accuracy:.3f}")
    logger.info(f"Precision: {precision:.3f}")  
    logger.info(f"Recall:    {recall:.3f}")
    logger.info(f"F1-Score:  {f1:.3f}")
    
    # 8. Matriz de confusión
    cm = confusion_matrix(y_true, y_pred)
    logger.info(f"Matriz de Confusión:")
    logger.info(f"TN: {cm[0,0]}, FP: {cm[0,1]}")
    logger.info(f"FN: {cm[1,0]}, TP: {cm[1,1]}")
    
    # 9. Generar visualizaciones
    os.makedirs('evaluation/', exist_ok=True)
    
    # Plot 1: Distribución de errores
    plt.figure(figsize=(12, 8))
    
    plt.subplot(2, 2, 1)
    plt.hist(reconstruction_errors[y_true == 0], bins=50, alpha=0.7, label='Normal', density=True)
    plt.hist(reconstruction_errors[y_true == 1], bins=50, alpha=0.7, label='Anomalía', density=True)
    plt.axvline(threshold, color='red', linestyle='--', label=f'Threshold: {threshold:.4f}')
    plt.xlabel('Error de Reconstrucción')
    plt.ylabel('Densidad')
    plt.legend()
    plt.title('Distribución de Errores de Reconstrucción')
    
    # Plot 2: Timeline de anomalías
    plt.subplot(2, 2, 2)
    window_timestamps = df_test['timestamp'][::stride][:len(X_test)]
    plt.scatter(window_timestamps[y_true == 0], reconstruction_errors[y_true == 0], 
                c='blue', alpha=0.6, label='Normal', s=20)
    plt.scatter(window_timestamps[y_true == 1], reconstruction_errors[y_true == 1], 
                c='red', alpha=0.8, label='Anomalía Real', s=30)
    plt.axhline(threshold, color='red', linestyle='--', alpha=0.7)
    plt.xticks(rotation=45)
    plt.ylabel('Error de Reconstrucción')
    plt.legend()
    plt.title('Timeline de Detección')
    
    # Plot 3: Matriz de confusión
    plt.subplot(2, 2, 3)
    sns.heatmap(cm, annot=True, fmt='d', cmap='Blues')
    plt.ylabel('Real')
    plt.xlabel('Predicción')
    plt.title('Matriz de Confusión')
    
    # Plot 4: Métricas
    plt.subplot(2, 2, 4)
    metrics = ['Accuracy', 'Precision', 'Recall', 'F1-Score']
    values = [accuracy, precision, recall, f1]
    bars = plt.bar(metrics, values, color=['green', 'blue', 'orange', 'red'])
    plt.ylim(0, 1.1)
    for bar, value in zip(bars, values):
        plt.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.01, 
                f'{value:.3f}', ha='center', va='bottom')
    plt.title('Métricas de Evaluación')
    plt.xticks(rotation=45)
    
    plt.tight_layout()
    plt.savefig('evaluation/model_evaluation.png', dpi=300, bbox_inches='tight')
    plt.show()
    
    logger.info("Visualizaciones guardadas en evaluation/model_evaluation.png")
    logger.info("=== Evaluación completada ===")
    
    return {
        'accuracy': accuracy,
        'precision': precision, 
        'recall': recall,
        'f1_score': f1,
        'threshold': threshold,
        'reconstruction_errors': reconstruction_errors
    }

if __name__ == "__main__":
    results = evaluate_model()
