from datetime import datetime, timedelta
from urllib.parse import quote

class GrafanaLinkGenerator:
    """
    Generador de enlaces contextuales a dashboards de Grafana
    """
    
    def __init__(self, base_url: str, dashboard_uid: str = None):
        self.base_url = base_url.rstrip('/')
        self.dashboard_uid = dashboard_uid or "tv-metrics-dashboard"
    
    def generate_anomaly_link(self, detection_time: str, 
                            time_range_minutes: int = 30) -> str:
        """
        Genera enlace a Grafana centrado en el tiempo de la anomalía
        """
        detection_dt = datetime.fromisoformat(detection_time.replace('Z', '+00:00'))
        
        start_time = detection_dt - timedelta(minutes=time_range_minutes // 2)
        end_time = detection_dt + timedelta(minutes=time_range_minutes // 2)
        
        start_ms = int(start_time.timestamp() * 1000)
        end_ms = int(end_time.timestamp() * 1000)
        
        params = f"from={start_ms}&to={end_ms}&refresh=30s"
        
        annotation = f"anomaly_detected_at_{int(detection_dt.timestamp())}"
        params += f"&var-annotation={quote(annotation)}"
        
        url = f"{self.base_url}/d/{self.dashboard_uid}?{params}"
        
        return url
