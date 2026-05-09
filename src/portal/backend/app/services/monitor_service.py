import requests
import datetime
import logging
from typing import Dict, Any

logger = logging.getLogger("Monitor")

class MonitorService:
    def __init__(self, prometheus_url: str):
        self.prometheus_url = prometheus_url

    def get_metrics(self) -> Dict[str, Any]:
        cpu_query = 'sum(rate(container_cpu_usage_seconds_total{namespace="vnf"}[2m])) * 100'
        mem_query = 'sum(container_memory_working_set_bytes{namespace="vnf"}) / 1024 / 1024'

        try:
            cpu_data = requests.get(f"{self.prometheus_url}/api/v1/query", params={'query': cpu_query}, timeout=2).json()
            mem_data = requests.get(f"{self.prometheus_url}/api/v1/query", params={'query': mem_query}, timeout=2).json()

            cpu_val = float(cpu_data['data']['result'][0]['value'][1]) if cpu_data['data']['result'] else 0
            mem_val = float(mem_data['data']['result'][0]['value'][1]) if mem_data['data']['result'] else 0

            return {
                "timestamp": datetime.datetime.now().strftime("%H:%M:%S"),
                "cpu": round(cpu_val, 2),
                "memory": round(mem_val, 2)
            }
        except Exception as e:
            logger.error(f"Failed to fetch metrics: {e}")
            return {"timestamp": "--:--", "cpu": 0, "memory": 0}