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

import re
import math
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
    
    # Maximum data points per query_range request (Prometheus default limit)
    MAX_QUERY_POINTS = 11000
    
    @staticmethod
    def _parse_step(step: str) -> int:
        """
        Parse a Prometheus step string into seconds.
        
        Args:
            step: Step string (e.g., '30s', '1m', '5m', '1h')
        
        Returns:
            int: Step duration in seconds
        
        Raises:
            ValueError: If the step string format is not recognized
        """
        match = re.match(r'^(\d+)([smhd])$', step.strip())
        if not match:
            raise ValueError(f"Invalid step format: '{step}'. Expected format like '30s', '1m', '5m', '1h'.")
        
        value = int(match.group(1))
        unit = match.group(2)
        multipliers = {'s': 1, 'm': 60, 'h': 3600, 'd': 86400}
        return value * multipliers[unit]
    
    def _adjust_step_if_needed(self, start_time: datetime, end_time: datetime, step: str) -> str:
        """
        Auto-adjust the query step if the time range would exceed Prometheus's
        maximum data points per query (11,000).
        
        Args:
            start_time: Start of the time range
            end_time: End of the time range
            step: Original step string
        
        Returns:
            str: Adjusted step string (unchanged if within limits)
        """
        step_seconds = self._parse_step(step)
        total_seconds = (end_time - start_time).total_seconds()
        n_points = total_seconds / step_seconds
        
        if n_points <= self.MAX_QUERY_POINTS:
            return step
        
        # Calculate minimum step to stay under the limit
        new_step_seconds = math.ceil(total_seconds / self.MAX_QUERY_POINTS)
        new_step = f"{new_step_seconds}s"
        
        print(f"Warning: query_range would return {int(n_points)} points (limit: {self.MAX_QUERY_POINTS}). "
              f"Auto-adjusting step from {step} to {new_step}.")
        
        return new_step
    
    def query_range(self, query: str, start_time: datetime, 
                   end_time: datetime, step: str = '30s', metric_name: str = None, 
                   aggregation: str = 'sum') -> pd.DataFrame:
        """
        Execute a range query on Prometheus.
        
        Fetches time series data for the specified PromQL query over
        a time range with configurable resolution. Automatically adjusts
        the step if the query would exceed Prometheus's 11,000-point limit.
        
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
        # Auto-adjust step to avoid exceeding Prometheus point limit
        step = self._adjust_step_if_needed(start_time, end_time, step)
        
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
    
    def get_tv_metrics(self, hours_back: float = 24, queries: List[Dict] = None,
                       step: str = '30s') -> pd.DataFrame:
        """
        Collect TV-over-IP service metrics from Prometheus.
        
        Fetches metrics defined in the queries parameter (typically loaded
        from config/data.yaml). Each query specifies a PromQL expression,
        a metric name, and an aggregation method.
        
        Args:
            hours_back: Number of hours of historical data to fetch.
                       Can be fractional (e.g., 0.5 for 30 minutes).
            queries: Optional list of query dicts from config, each with keys:
                     - 'query': PromQL expression
                     - 'name': metric column name
                     - 'aggregation': how to combine series ('sum', 'mean', 'max')
                     If None, uses built-in default queries.
            step: Query resolution step (e.g., '30s', '1m'). Passed through
                  to query_range() which auto-adjusts if needed.
        
        Returns:
            pd.DataFrame: Combined metrics with timestamp index.
                         Returns empty DataFrame if all queries fail.
        """
        end_time = datetime.now()
        start_time = end_time - timedelta(hours=hours_back)
        
        # Default queries if none provided (matches config/data.yaml)
        if queries is None:
            query_list = [
                ('rate(http_requests_total[5m])', 'request_rate', 'sum'),
                ('histogram_quantile(0.95, rate(http_request_duration_seconds_bucket[5m]))', 'latency_p95', 'max'),
                ('process_resident_memory_bytes', 'memory_usage', 'mean'),
                ('rate(http_request_errors_total[5m])', 'error_rate', 'sum'),
                ('rate(process_cpu_seconds_total[5m])', 'cpu_usage', 'sum'),
            ]
        else:
            # Convert config dicts to tuples: (query_str, name, aggregation)
            query_list = [
                (q['query'], q['name'], q.get('aggregation', 'sum'))
                for q in queries
            ]
        
        all_metrics = []
        for query_str, metric_name, aggregation in query_list:
            try:
                df = self.query_range(query_str, start_time, end_time, step=step,
                                      metric_name=metric_name, aggregation=aggregation)
                if not df.empty:
                    all_metrics.append(df)
            except Exception as e:
                print(f"Warning: Failed to fetch query '{query_str}': {e}")
        
        if all_metrics:
            combined = all_metrics[0]
            for df in all_metrics[1:]:
                combined = combined.merge(df, on='timestamp', how='outer')
            
            return combined.sort_values('timestamp').fillna(method='ffill').fillna(0)
        
        return pd.DataFrame()
