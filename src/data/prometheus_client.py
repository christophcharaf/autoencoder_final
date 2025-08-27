import requests
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import List, Dict, Optional
import time

class PrometheusClient:
    """
    Cliente para conectarse a Prometheus y recopilar métricas
    """
    
    def __init__(self, base_url: str, token: str = None):
        self.base_url = base_url.rstrip('/')
        self.session = requests.Session()
        if token:
            self.session.headers.update({'Authorization': f'Bearer {token}'})
    
    def query_range(self, query: str, start_time: datetime, 
                   end_time: datetime, step: str = '30s') -> pd.DataFrame:
        """
        Ejecuta query de rango en Prometheus
        """
        url = f"{self.base_url}/api/v1/query_range"
        
        params = {
            'query': query,
            'start': start_time.timestamp(),
            'end': end_time.timestamp(), 
            'step': step
        }
        
        try:
            response = self.session.get(url, params=params, timeout=30)
            response.raise_for_status()
            
            data = response.json()
            if data['status'] != 'success':
                raise Exception(f"Prometheus query failed: {data.get('error', 'Unknown error')}")
            
            return self._parse_prometheus_response(data['data']['result'])
            
        except requests.exceptions.RequestException as e:
            raise Exception(f"Error connecting to Prometheus: {e}")
    
    def _parse_prometheus_response(self, results: List[Dict]) -> pd.DataFrame:
        """
        Convierte respuesta de Prometheus a DataFrame
        """
        if not results:
            return pd.DataFrame()
        
        dfs = []
        for result in results:
            metric_name = result['metric'].get('__name__', 'unknown')
            values = result['values']
            
            df = pd.DataFrame(values, columns=['timestamp', 'value'])
            df['timestamp'] = pd.to_datetime(df['timestamp'], unit='s')
            df['value'] = pd.to_numeric(df['value'], errors='coerce')
            df['metric'] = metric_name
            
            dfs.append(df)
        
        if dfs:
            combined = pd.concat(dfs, ignore_index=True)
            # Pivot para tener métricas como columnas
            pivoted = combined.pivot(index='timestamp', columns='metric', values='value')
            pivoted.reset_index(inplace=True)
            return pivoted.fillna(0)
        
        return pd.DataFrame()
    
    def get_tv_metrics(self, hours_back: int = 24) -> pd.DataFrame:
        """
        Recopila métricas típicas de TV-over-IP
        """
        end_time = datetime.now()
        start_time = end_time - timedelta(hours=hours_back)
        
        # Queries típicas para TV-over-IP
        queries = [
            'rate(http_requests_total[5m])',
            'histogram_quantile(0.95, http_request_duration_seconds)',
            'up',
            'process_resident_memory_bytes',
            'rate(http_request_errors_total[5m])',
        ]
        
        all_metrics = []
        for query in queries:
            try:
                df = self.query_range(query, start_time, end_time)
                if not df.empty:
                    all_metrics.append(df)
            except Exception as e:
                print(f"Warning: Failed to fetch query '{query}': {e}")
        
        if all_metrics:
            combined = all_metrics[0]
            for df in all_metrics[1:]:
                combined = combined.merge(df, on='timestamp', how='outer')
            
            return combined.sort_values('timestamp').fillna(method='ffill').fillna(0)
        
        return pd.DataFrame()
