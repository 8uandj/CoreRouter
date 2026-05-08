import numpy as np
import torch
import torch.nn as nn
import time
import requests
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("Forecaster")

THRESHOLD = 800  
FASTAPI_URL = "http://127.0.0.1:8000/api/deploy" 

class BiGRUForecaster(nn.Module):
    def __init__(self, input_dim=1, hidden_dim=16, output_dim=1, num_layers=1):
        super(BiGRUForecaster, self).__init__()
        self.gru = nn.GRU(input_dim, hidden_dim, num_layers, batch_first=True, bidirectional=True)
        self.fc = nn.Linear(hidden_dim * 2, output_dim)

    def forward(self, x):
        out, _ = self.gru(x)
        out = self.fc(out[:, -1, :])
        return out

def run_analytics_pipeline():
    logger.info("Initializing Bi-GRU Proactive Forecaster")
    
    model = BiGRUForecaster()
    model.eval()
    
    sequence = [300.0, 450.0, 500.0, 680.0, 750.0]
    
    for step in range(5):
        time.sleep(1)
        input_tensor = torch.tensor(sequence, dtype=torch.float32).view(1, 5, 1)
        
        with torch.no_grad():
            pred = model(input_tensor).item()
            
        logger.info(f"[t={step}s] Current: {int(sequence[-1])} pps -> Pred t+1: {int(pred)} pps")
        
        if pred > THRESHOLD:
            logger.warning("Traffic threshold breach predicted. Activating proactive migration.")
            try:
                requests.post(FASTAPI_URL, json={"name": "proactive-mig-v1", "type": "migrate"})
                logger.info("Migration command sent to orchestrator.")
            except Exception:
                logger.error("Backend unreachable for migration command.")
            break
            
        new_val = sequence[-1] + np.random.randint(20, 80)
        sequence.append(float(new_val))
        sequence.pop(0)

if __name__ == "__main__":
    run_analytics_pipeline()