"""
Prometheus Client for Metric Collection

This module provides a client for connecting to Prometheus and fetching
time series metrics for the anomaly detection system.

The client supports:
    - Range queries for historical data (training)
    - Authentication via Bearer token
    - Configurable timeout for robustness
    - Automatic parsing of Prometheus response format
"""

import requests
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import List, Dict, Optional


class PrometheusClient:
    """
    Client for connecting to Prometheus and collecting metrics.
    
    Fetches time series data from Prometheus using the HTTP API.
    Supports both authenticated and unauthenticated connections.
    
    Attributes:
        base_url: Prometheus server URL (e.g., 'http://prometheus:9090')
        timeout: Request timeout in seconds
        session: Requests session with configured authentication
    
    Example:
        >>> client = PrometheusClient('http://prometheus:9090', token='my_token')
        >>> df = client.get_tv_metrics(hours_back=24)
    """
    
    def __init__(self, base_url: str, token: str = None, timeout: int = 30):
        """
        Initialize the Prometheus client.
        
        Args:
            base_url: Prometheus server URL
            token: Optional Bearer token for authentication
            timeout: Request timeout in seconds (default: 30)
        """
        self.base_url = base_url.rstrip('/')
        self.timeout = timeout
        self.session = requests.Session()
        
        # Configure authentication if token provided
        if token:
            self.session.headers.update({'Authorization': f'Bearer {token}'})
    
    def query_range(self, query: str, start_time: datetime, 
                   end_time: datetime, step: str = '30s', metric_name: str = None, 
                   aggregation: str = 'sum') -> pd.DataFrame:
        """
        Execute a range query on Prometheus.
        
        Fetches time series data for the specified PromQL query over
        a time range with configurable resolution.
        
        Args:
            query: PromQL query string (e.g., 'rate(http_requests_total[5m])')
            start_time: Start of the time range
            end_time: End of the time range
            step: Query resolution step (e.g., '30s', '1m', '5m')
            metric_name: Optional explicit name for the metric column
            aggregation: How to combine multiple time series ('sum', 'mean', 'max')
        
        Returns:
            pd.DataFrame: Time series data with timestamp and metric columns
        
        Raises:
            Exception: If Prometheus query fails or connection error occurs
        """
        url = f"{self.base_url}/api/v1/query_range"
        
        params = {
            'query': query,
            'start': start_time.timestamp(),
            'end': end_time.timestamp(), 
            'step': step
        }
        
        try:
            response = self.session.get(url, params=params, timeout=self.timeout)
            response.raise_for_status()
            
            data = response.json()
            if data['status'] != 'success':
                raise Exception(f"Prometheus query failed: {data.get('error', 'Unknown error')}")
            
            return self._parse_prometheus_response(data['data']['result'], metric_name=metric_name, aggregation=aggregation)
            
        except requests.exceptions.RequestException as e:
            raise Exception(f"Error connecting to Prometheus: {e}")
    
    def _parse_prometheus_response(self, results: List[Dict], metric_name: str = None, 
                                    aggregation: str = 'sum') -> pd.DataFrame:
        """
        Parse Prometheus API response into a pandas DataFrame.
        
        Converts the nested JSON response format into a flat DataFrame
        with timestamp index and one column per metric. When multiple time series
        exist for the same metric (e.g., different endpoints), aggregates using
        the specified method.
        
        Args:
            results: List of result dictionaries from Prometheus API
            metric_name: Optional explicit metric name to use (overrides __name__ from response)
            aggregation: Aggregation method when multiple series exist. Options:
                        'sum' (default) - sum values (good for rates, counts)
                        'mean' - average values (good for latency)
                        'max' - maximum value (good for worst-case latency)
        
        Returns:
            pd.DataFrame: Parsed data with timestamp and metric value columns
        """
        if not results:
            return pd.DataFrame()
        
        # If explicit metric name provided, use it for all results and aggregate
        if metric_name:
            all_values = []
            for result in results:
                values = result['values']
                for timestamp, value in values:
                    all_values.append({
                        'timestamp': pd.to_datetime(timestamp, unit='s'),
                        'value': float(value)
                    })
            
            if not all_values:
                return pd.DataFrame()
            
            df = pd.DataFrame(all_values)
            # Aggregate duplicate timestamps using specified method
            if aggregation == 'mean':
                aggregated = df.groupby('timestamp')['value'].mean().reset_index()
            elif aggregation == 'max':
                aggregated = df.groupby('timestamp')['value'].max().reset_index()
            else:  # default: sum
                aggregated = df.groupby('timestamp')['value'].sum().reset_index()
            
            aggregated.columns = ['timestamp', metric_name]
            return aggregated
        
        # Fallback to original behavior if no explicit name
        dfs = []
        for result in results:
            name = result['metric'].get('__name__', 'unknown')
            values = result['values']
            
            df = pd.DataFrame(values, columns=['timestamp', 'value'])
            df['timestamp'] = pd.to_datetime(df['timestamp'], unit='s')
            df['value'] = pd.to_numeric(df['value'], errors='coerce')
            df['metric'] = name
            
            dfs.append(df)
        
        if dfs:
            combined = pd.concat(dfs, ignore_index=True)
            aggregated = combined.groupby(['timestamp', 'metric'])['value'].sum().reset_index()
            pivoted = aggregated.pivot(index='timestamp', columns='metric', values='value')
            pivoted.reset_index(inplace=True)
            return pivoted.fillna(0)
        
        return pd.DataFrame()
    
    def get_tv_metrics(self, hours_back: float = 24) -> pd.DataFrame:
        """
        Collect typical TV-over-IP service metrics.
        
        Fetches a predefined set of metrics commonly used for monitoring
        TV streaming services:
            - Request rate (requests per second)
            - Latency P95 (95th percentile response time)
            - Service availability (up/down status)
            - Memory usage (resident memory in bytes)
            - Error rate (errors per second)
        
        Args:
            hours_back: Number of hours of historical data to fetch.
                       Can be fractional (e.g., 0.5 for 30 minutes).
        
        Returns:
            pd.DataFrame: Combined metrics with timestamp index.
                         Returns empty DataFrame if all queries fail.
        """
        end_time = datetime.now()
        start_time = end_time - timedelta(hours=hours_back)
        
        # PromQL queries for TV-over-IP service metrics with explicit names
        # Note: Must match the columns used during training
        # Format: (query, metric_name, aggregation_method)
        # - sum: for rates/counts (request_rate, error_rate, cpu_usage)
        # - max: for worst-case latency across endpoints
        # - mean: for averaging gauges (memory_usage)
        queries = [
            ('rate(http_requests_total[5m])', 'request_rate', 'sum'),
            ('histogram_quantile(0.95, rate(http_request_duration_seconds_bucket[5m]))', 'latency_p95', 'max'),
            ('process_resident_memory_bytes', 'memory_usage', 'mean'),
            ('rate(http_request_errors_total[5m])', 'error_rate', 'sum'),
            ('rate(process_cpu_seconds_total[5m])', 'cpu_usage', 'sum'),
        ]
        
        all_metrics = []
        for query, metric_name, aggregation in queries:
            try:
                df = self.query_range(query, start_time, end_time, metric_name=metric_name, aggregation=aggregation)
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
