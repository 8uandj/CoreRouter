import csv
import os
from typing import List, Dict, Any
from src.core.interfaces.repository import IRepository

class CSVRepository(IRepository):
    def __init__(self, default_path: str = None):
        self.dataset: List[Dict[str, Any]] = []
        if default_path:
            self.load_data(default_path)

    def load_data(self, path: str) -> List[Dict[str, Any]]:
        if not os.path.exists(path):
            return []
        
        self.dataset = []
        with open(path, 'r') as f:
            reader = csv.DictReader(f)
            for row in reader:
                try:
                    # Provide defaults for missing columns
                    svc_type = row.get('service_type', 'Data')
                    priority = int(row.get('priority', 1)) if row.get('priority') else 1

                    self.dataset.append({
                        'cpu': float(row['cpu_req']),
                        'ram': float(row['ram_req']),
                        'msd': int(row['msd_req']),
                        'ddos': int(row['is_ddos_spike']),
                        'service_type': svc_type,
                        'priority': priority
                    })
                except (KeyError, ValueError):
                    continue
        return self.dataset

    def get_next_entry(self, index: int) -> Dict[str, Any]:
        if not self.dataset:
            return {'cpu': 10.0, 'ram': 5.0, 'msd': 2, 'ddos': 0, 'service_type': 'Data', 'priority': 1}
        return self.dataset[index % len(self.dataset)]
