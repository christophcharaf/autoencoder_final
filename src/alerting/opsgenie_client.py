import requests
import json
from typing import Dict
from datetime import datetime

class OpsgenieClient:
    """
    Client for sending anomaly alerts to Opsgenie.

    Supports normal anomaly alerts, escalation alerts for long-running anomalies,
    and resolved notifications when anomalies clear.
    """
    
    def __init__(self, api_key: str, base_url: str = "https://api.opsgenie.com",
                 timeout: int = 10, priority_thresholds: Dict = None):
        self.api_key = api_key
        self.base_url = base_url.rstrip('/')
        self.timeout = timeout
        self.priority_thresholds = priority_thresholds or {'P1': 2.0, 'P2': 1.0, 'P3': 0.5}
        self.headers = {
            'Authorization': f'GenieKey {api_key}',
            'Content-Type': 'application/json'
        }
    
    def create_alert(self, detection_result: Dict, grafana_link: str = None) -> Dict:
        """
        Create an Opsgenie alert from anomaly detection result.
        """
        if not detection_result.get('is_anomaly', False):
            return {'status': 'skipped', 'reason': 'Not an anomaly'}
        
        error_value = detection_result['reconstruction_error']
        threshold = detection_result['threshold']
        confidence = detection_result.get('confidence', 0)
        is_escalation = detection_result.get('is_escalation', False)
        
        # Check if this is an escalation alert
        if is_escalation:
            duration = detection_result.get('duration_minutes', 0)
            initial_error = detection_result.get('initial_error', error_value)
            
            description = f"""
⚠️ ESCALATION: Anomaly still active on TV-over-IP service

⏱️ Duration: {duration} minutes
🔍 Details:
- Current error: {error_value:.4f}
- Initial error: {initial_error:.4f}
- Threshold: {threshold:.4f}
- Confidence: {confidence:.2f}
- Timestamp: {detection_result['timestamp']}

📊 Affected metrics:
{self._format_metrics_comparison(detection_result)}
            """.strip()
            
            alert_payload = {
                'message': f'⚠️ ESCALATION: TV-over-IP Anomaly ongoing for {duration} minutes',
                'description': description,
                'priority': 'P2',  # Bump priority for escalations
                'tags': ['anomaly-detection', 'tv-over-ip', 'lstm-autoencoder', 'escalation'],
            }
        else:
            # Normal anomaly alert
            description = f"""
Anomaly detected on TV-over-IP service

🔍 Details:
- Reconstruction error: {error_value:.4f}
- Threshold: {threshold:.4f}
- Confidence: {confidence:.2f}
- Timestamp: {detection_result['timestamp']}

📊 Affected metrics:
{self._format_metrics_comparison(detection_result)}
            """.strip()

            alert_payload = {
                'message': 'Anomaly detected on TV-over-IP',
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
            alert_payload['description'] += f"\n\n📈 View in Grafana: {grafana_link}"
            if 'details' not in alert_payload:
                alert_payload['details'] = {}
            alert_payload['details']['grafana_link'] = grafana_link
        
        try:
            response = requests.post(
                f"{self.base_url}/v2/alerts",
                headers=self.headers,
                data=json.dumps(alert_payload),
                timeout=self.timeout
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
        """Determine alert priority from confidence (configurable thresholds)."""
        if confidence > self.priority_thresholds.get('P1', 2.0):
            return 'P1'
        elif confidence > self.priority_thresholds.get('P2', 1.0):
            return 'P2'
        elif confidence > self.priority_thresholds.get('P3', 0.5):
            return 'P3'
        else:
            return 'P4'
    
    def _format_metrics_comparison(self, detection_result: Dict) -> str:
        """Format original vs reconstructed metrics for alert description."""
        if 'feature_columns' not in detection_result:
            return "Metric data not available"

        original = detection_result.get('original_values', [])
        reconstructed = detection_result.get('reconstructed_values', [])
        features = detection_result['feature_columns']

        if not original or not reconstructed or not features:
            return "Comparison data not available"
        
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
        
        return "Could not process metrics"
    
    def create_resolved_alert(self, resolved_data: Dict) -> Dict:
        """Create resolved notification in Opsgenie"""
        duration = resolved_data.get('duration_seconds', 0)
        duration_str = f"{duration//60}m {duration%60}s"
        
        description = f"""
Anomaly resolved on TV-over-IP service

✅ Status: Resolved
⏱️ Duration: {duration_str}
🆔 Anomaly ID: {resolved_data.get('anomaly_id', 'N/A')}
📊 Initial error: {resolved_data.get('initial_error', 0):.4f}
        """.strip()

        alert_payload = {
            'message': '✅ Anomaly resolved on TV-over-IP',
            'description': description,
            'priority': 'P5',
            'tags': ['anomaly-detection', 'tv-over-ip', 'resolved'],
            'details': {
                'status': 'resolved',
                'duration_seconds': duration,
                'initial_error': resolved_data.get('initial_error'),
                'anomaly_id': resolved_data.get('anomaly_id'),
                'resolved_at': resolved_data.get('timestamp')
            }
        }
        
        try:
            response = requests.post(
                f"{self.base_url}/v2/alerts",
                headers=self.headers,
                data=json.dumps(alert_payload),
                timeout=self.timeout
            )
            response.raise_for_status()
            
            return {
                'status': 'success',
                'alert_id': response.json().get('requestId')
            }
        except requests.exceptions.RequestException as e:
            return {
                'status': 'error',
                'error': str(e)
            }
