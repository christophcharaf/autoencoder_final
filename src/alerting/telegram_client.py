"""
Telegram alert client for the LSTM Autoencoder anomaly detector.

Provides the same interface as OpsgenieClient (create_alert / create_resolved_alert)
so the inference service can switch alert backends via config (alerting.provider).

Telegram was added as a reproducible, openly available alert channel after
Atlassian announced Opsgenie's end of life (no new sign-ups since June 2025;
full shutdown on April 5, 2027). Because the alerting layer is HTTP-based, the
channel is pluggable: the same detection payload is delivered to a Telegram bot
via the Bot API instead of the Opsgenie REST API.
"""

import requests
from typing import Dict


class TelegramClient:
    """
    Client for sending anomaly alerts to a Telegram chat via the Bot API.

    Mirrors OpsgenieClient: create_alert() for new/escalation alerts and
    create_resolved_alert() for resolution notices. Messages are sent with
    sendMessage to https://api.telegram.org/bot<token>/sendMessage.
    """

    def __init__(self, bot_token: str, chat_id: str, base_url: str = "https://api.telegram.org",
                 timeout: int = 10, priority_thresholds: Dict = None):
        self.bot_token = bot_token
        self.chat_id = chat_id
        self.base_url = base_url.rstrip('/')
        self.timeout = timeout
        self.priority_thresholds = priority_thresholds or {'P1': 2.0, 'P2': 1.0, 'P3': 0.5}

    def _send_message(self, text: str) -> Dict:
        """Send a plain-text message to the configured chat."""
        url = f"{self.base_url}/bot{self.bot_token}/sendMessage"
        payload = {
            'chat_id': self.chat_id,
            'text': text,
            'disable_web_page_preview': False,
        }
        try:
            response = requests.post(url, json=payload, timeout=self.timeout)
            response.raise_for_status()
            data = response.json()
            return {
                'status': 'success',
                'alert_id': str(data.get('result', {}).get('message_id', '')),
                'response': data,
            }
        except requests.exceptions.RequestException as e:
            return {
                'status': 'error',
                'error': str(e),
                'payload': payload,
            }

    def create_alert(self, detection_result: Dict, grafana_link: str = None) -> Dict:
        """Send a new-anomaly or escalation alert to Telegram."""
        if not detection_result.get('is_anomaly', False):
            return {'status': 'skipped', 'reason': 'Not an anomaly'}

        error_value = detection_result['reconstruction_error']
        threshold = detection_result['threshold']
        confidence = detection_result.get('confidence', 0)
        is_escalation = detection_result.get('is_escalation', False)

        if is_escalation:
            duration = detection_result.get('duration_minutes', 0)
            initial_error = detection_result.get('initial_error', error_value)
            text = (
                f"\u26a0\ufe0f ESCALATION: anomaly still active on TV-over-IP service\n\n"
                f"Duration: {duration} minutes\n"
                f"Current error: {error_value:.4f}\n"
                f"Initial error: {initial_error:.4f}\n"
                f"Threshold: {threshold:.4f}\n"
                f"Confidence: {confidence:.2f}\n"
                f"Priority: P2\n"
                f"Timestamp: {detection_result['timestamp']}\n\n"
                f"Affected metrics:\n{self._format_metrics_comparison(detection_result)}"
            )
        else:
            priority = self._determine_priority(confidence)
            text = (
                f"\U0001f6a8 Anomaly detected on TV-over-IP service\n\n"
                f"Reconstruction error: {error_value:.4f}\n"
                f"Threshold: {threshold:.4f}\n"
                f"Confidence: {confidence:.2f}\n"
                f"Priority: {priority}\n"
                f"Timestamp: {detection_result['timestamp']}\n\n"
                f"Affected metrics:\n{self._format_metrics_comparison(detection_result)}"
            )

        if grafana_link:
            text += f"\n\n\U0001f4c8 View in Grafana: {grafana_link}"

        return self._send_message(text)

    def create_resolved_alert(self, resolved_data: Dict) -> Dict:
        """Send a resolution notice to Telegram."""
        duration = resolved_data.get('duration_seconds', 0)
        duration_str = f"{duration // 60}m {duration % 60}s"
        text = (
            f"\u2705 Anomaly resolved on TV-over-IP service\n\n"
            f"Duration: {duration_str}\n"
            f"Anomaly ID: {resolved_data.get('anomaly_id', 'N/A')}\n"
            f"Initial error: {resolved_data.get('initial_error', 0):.4f}"
        )
        return self._send_message(text)

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
        """Format original vs reconstructed metrics for the message body."""
        if 'feature_columns' not in detection_result:
            return "Metric data not available"

        original = detection_result.get('original_values', [])
        reconstructed = detection_result.get('reconstructed_values', [])
        features = detection_result['feature_columns']

        if not original or not reconstructed or not features:
            return "Comparison data not available"

        if len(original) > 0 and len(original[0]) > 0:
            last_original = original[-1] if isinstance(original[0], list) else original
            last_reconstructed = reconstructed[-1] if isinstance(reconstructed[0], list) else reconstructed

            comparison = []
            for i, feature in enumerate(features[:min(len(features), len(last_original))]):
                orig_val = last_original[i] if i < len(last_original) else 0
                recon_val = last_reconstructed[i] if i < len(last_reconstructed) else 0
                diff = abs(orig_val - recon_val)
                comparison.append(f"  {feature}: {orig_val:.3f} -> {recon_val:.3f} (diff: {diff:.3f})")

            return "\n".join(comparison[:5])

        return "Could not process metrics"
