import requests
import json
from typing import Dict
from datetime import datetime

class OpsgenieClient:
    """
    Cliente para enviar alertas a Opsgenie
    """
    
    def __init__(self, api_key: str, base_url: str = "https://api.opsgenie.com"):
        self.api_key = api_key
        self.base_url = base_url.rstrip('/')
        self.headers = {
            'Authorization': f'GenieKey {api_key}',
            'Content-Type': 'application/json'
        }
    
    def create_alert(self, detection_result: Dict, grafana_link: str = None) -> Dict:
        """
        Crea alerta en Opsgenie basada en detección de anomalía
        """
        if not detection_result.get('is_anomaly', False):
            return {'status': 'skipped', 'reason': 'Not an anomaly'}
        
        error_value = detection_result['reconstruction_error']
        threshold = detection_result['threshold']
        confidence = detection_result.get('confidence', 0)
        
        description = f"""
Anomalía detectada en servicio TV-over-IP

🔍 Detalles:
- Error de reconstrucción: {error_value:.4f}
- Umbral configurado: {threshold:.4f} 
- Confianza: {confidence:.2f}
- Timestamp: {detection_result['timestamp']}

📊 Métricas afectadas:
{self._format_metrics_comparison(detection_result)}
        """.strip()
        
        alert_payload = {
            'message': 'Anomalía detectada en TV-over-IP',
            'description': description,
            'priority': self._determine_priority(confidence),
            'tags': ['anomaly-detection', 'tv-over-ip', 'lstm-autoencoder'],
            'details': {
                'reconstruction_error': error_value,
                'threshold': threshold,
                'confidence': confidence,
                'detection_time': detection_result['timestamp'],
                'service': 'tv-over-ip'
            }
        }
        
        if grafana_link:
            alert_payload['description'] += f"\n\n📈 Ver en Grafana: {grafana_link}"
            alert_payload['details']['grafana_link'] = grafana_link
        
        try:
            response = requests.post(
                f"{self.base_url}/v2/alerts",
                headers=self.headers,
                data=json.dumps(alert_payload),
                timeout=10
            )
            response.raise_for_status()
            
            return {
                'status': 'success',
                'alert_id': response.json().get('requestId'),
                'response': response.json()
            }
            
        except requests.exceptions.RequestException as e:
            return {
                'status': 'error',
                'error': str(e),
                'payload': alert_payload
            }
    
    def _determine_priority(self, confidence: float) -> str:
        """Determina prioridad basada en confianza"""
        if confidence > 2.0:
            return 'P1'
        elif confidence > 1.0:
            return 'P2'
        elif confidence > 0.5:
            return 'P3'
        else:
            return 'P4'
    
    def _format_metrics_comparison(self, detection_result: Dict) -> str:
        """Formatea comparación de métricas"""
        if 'feature_columns' not in detection_result:
            return "Datos de métricas no disponibles"
        
        original = detection_result.get('original_values', [])
        reconstructed = detection_result.get('reconstructed_values', [])
        features = detection_result['feature_columns']
        
        if not original or not reconstructed or not features:
            return "Datos de comparación no disponibles"
        
        # Mostrar solo las últimas mediciones
        if len(original) > 0 and len(original[0]) > 0:
            last_original = original[-1] if isinstance(original[0], list) else original
            last_reconstructed = reconstructed[-1] if isinstance(reconstructed[0], list) else reconstructed
            
            comparison = []
            for i, feature in enumerate(features[:min(len(features), len(last_original))]):
                orig_val = last_original[i] if i < len(last_original) else 0
                recon_val = last_reconstructed[i] if i < len(last_reconstructed) else 0
                diff = abs(orig_val - recon_val)
                comparison.append(f"  {feature}: {orig_val:.3f} → {recon_val:.3f} (diff: {diff:.3f})")
            
            return "\n".join(comparison[:5])
        
        return "No se pudieron procesar las métricas"
