"""
Jira Service Management (JSM) Operations alert client.

JSM is the successor of Opsgenie, which Atlassian retired (no new sign-ups since
June 2025; full shutdown on April 5, 2027). The JSM Operations *integration*
endpoint is Opsgenie-compatible: it uses the same ``GenieKey`` authentication
header and the same alert payload schema. This client therefore mirrors
``OpsgenieClient`` (and reuses its priority/metrics helpers); it only changes the
base URL and sets an ``alias`` (the anomaly id) so the resolution can close the
same alert via the close-by-alias endpoint.

Endpoints (base ``https://api.atlassian.com/jsm/ops/integration``):
  POST /v2/alerts
  POST /v2/alerts/{alias}/close?identifierType=alias
Auth: ``Authorization: GenieKey <integration api key>``
"""

import json
import requests
from typing import Dict

from alerting.opsgenie_client import OpsgenieClient


class JSMClient(OpsgenieClient):
    """JSM Operations alert client (Opsgenie-compatible integration endpoint)."""

    DEFAULT_ALIAS = "tv-over-ip-anomaly"

    def __init__(self, api_key: str,
                 base_url: str = "https://api.atlassian.com/jsm/ops/integration",
                 timeout: int = 10, priority_thresholds: Dict = None):
        super().__init__(api_key, base_url=base_url, timeout=timeout,
                         priority_thresholds=priority_thresholds)

    def _alias(self, data: Dict) -> str:
        """Stable alias per anomaly so open and close target the same alert."""
        return str(data.get('anomaly_id') or self.DEFAULT_ALIAS)

    def create_alert(self, detection_result: Dict, grafana_link: str = None) -> Dict:
        """Create a new-anomaly or escalation alert in JSM Operations."""
        if not detection_result.get('is_anomaly', False):
            return {'status': 'skipped', 'reason': 'Not an anomaly'}

        error_value = detection_result['reconstruction_error']
        threshold = detection_result['threshold']
        confidence = detection_result.get('confidence', 0)
        is_escalation = detection_result.get('is_escalation', False)
        alias = self._alias(detection_result)

        if is_escalation:
            duration = detection_result.get('duration_minutes', 0)
            initial_error = detection_result.get('initial_error', error_value)
            message = f'\u26a0\ufe0f ESCALATION: TV-over-IP anomaly ongoing for {duration} minutes'
            description = (
                f"ESCALATION: Anomaly still active on TV-over-IP service\n\n"
                f"Duration: {duration} minutes\n"
                f"Current error: {error_value:.4f}\n"
                f"Initial error: {initial_error:.4f}\n"
                f"Threshold: {threshold:.4f}\n"
                f"Confidence: {confidence:.2f}\n"
                f"Timestamp: {detection_result['timestamp']}\n\n"
                f"Affected metrics:\n{self._format_metrics_comparison(detection_result)}"
            )
            priority = 'P2'
            tags = ['anomaly-detection', 'tv-over-ip', 'lstm-autoencoder', 'escalation']
        else:
            message = 'Anomaly detected on TV-over-IP'
            description = (
                f"Anomaly detected on TV-over-IP service\n\n"
                f"Reconstruction error: {error_value:.4f}\n"
                f"Threshold: {threshold:.4f}\n"
                f"Confidence: {confidence:.2f}\n"
                f"Timestamp: {detection_result['timestamp']}\n\n"
                f"Affected metrics:\n{self._format_metrics_comparison(detection_result)}"
            )
            priority = self._determine_priority(confidence)
            tags = ['anomaly-detection', 'tv-over-ip', 'lstm-autoencoder']

        # JSM/Opsgenie require `details` to be a map of string -> string.
        payload = {
            'message': message,
            'alias': alias,
            'description': description,
            'priority': priority,
            'tags': tags,
            'details': {
                'reconstruction_error': f"{error_value:.6f}",
                'threshold': f"{threshold:.6f}",
                'confidence': f"{confidence:.4f}",
                'detection_time': str(detection_result['timestamp']),
                'service': 'tv-over-ip',
            },
        }
        if grafana_link:
            payload['description'] += f"\n\n\U0001f4c8 View in Grafana: {grafana_link}"
            payload['details']['grafana_link'] = str(grafana_link)

        return self._post(f"{self.base_url}/v2/alerts", payload)

    def create_resolved_alert(self, resolved_data: Dict) -> Dict:
        """Close the alert in JSM Operations by alias when the anomaly clears."""
        alias = self._alias(resolved_data)
        duration = resolved_data.get('duration_seconds', 0)
        note = (
            f"Anomaly resolved after {duration // 60}m {duration % 60}s "
            f"(id {resolved_data.get('anomaly_id', 'N/A')}, "
            f"initial error {resolved_data.get('initial_error', 0):.4f})"
        )
        url = f"{self.base_url}/v2/alerts/{alias}/close"
        try:
            response = requests.post(
                url,
                headers=self.headers,
                params={'identifierType': 'alias'},
                data=json.dumps({'note': note}),
                timeout=self.timeout,
            )
            response.raise_for_status()
            data = response.json()
            return {'status': 'success', 'alert_id': data.get('requestId'), 'response': data}
        except requests.exceptions.RequestException as e:
            return {'status': 'error', 'error': str(e)}

    def _post(self, url: str, payload: Dict) -> Dict:
        """POST a JSON payload and normalize the response (returns requestId)."""
        try:
            response = requests.post(
                url,
                headers=self.headers,
                data=json.dumps(payload),
                timeout=self.timeout,
            )
            response.raise_for_status()
            data = response.json()
            return {'status': 'success', 'alert_id': data.get('requestId'), 'response': data}
        except requests.exceptions.RequestException as e:
            return {'status': 'error', 'error': str(e), 'payload': payload}
