import requests
import datetime
from app.core.config import settings

def get_metrics():
    # Rate tính trong 2 phút gần nhất
    cpu_query = 'sum(rate(container_cpu_usage_seconds_total{namespace="vnf"}[2m])) * 100'
    mem_query = 'sum(container_memory_working_set_bytes{namespace="vnf"}) / 1024 / 1024'

    try:
        cpu_data = requests.get(f"{settings.PROMETHEUS_URL}/api/v1/query", params={'query': cpu_query}, timeout=2).json()
        mem_data = requests.get(f"{settings.PROMETHEUS_URL}/api/v1/query", params={'query': mem_query}, timeout=2).json()

        cpu_val = float(cpu_data['data']['result'][0]['value'][1]) if cpu_data['data']['result'] else 0
        mem_val = float(mem_data['data']['result'][0]['value'][1]) if mem_data['data']['result'] else 0

        return {
            "timestamp": datetime.datetime.now().strftime("%H:%M:%S"),
            "cpu": round(cpu_val, 2),
            "memory": round(mem_val, 2)
        }
    except Exception:
        return {"timestamp": "--:--", "cpu": 0, "memory": 0}