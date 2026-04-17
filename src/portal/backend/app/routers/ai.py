from fastapi import APIRouter, BackgroundTasks
import asyncio
import logging
from src.portal.backend.app.containers.service_container import container

logger = logging.getLogger("AI-Loop")
router = APIRouter(tags=["AI Simulation"])

AI_STATE = {
    "running": False,
    "current_score": 0.0,
    "status": "NORMAL",
    "logs": []
}

def generate_demo_data():
    data = []
    # NORMAL
    for _ in range(5):
        data.append([0.01, 1, 120, 240, 5])
    # ATTACK
    for _ in range(20):
        data.append([5.5, 1, 9500, 8800, 500])
    # RECOVERY
    for _ in range(5):
        data.append([0.02, 1, 110, 250, 4])
    return data

async def replay_traffic_loop():
    dataset = generate_demo_data()
    logger.info(f"Starting Traffic Replay with {len(dataset)} samples.")

    try:
        for index, features in enumerate(dataset):
            if not AI_STATE["running"]: 
                break
            
            result, score = container.ai_service.predict_and_react(features)
            
            AI_STATE["current_score"] = float(score)
            AI_STATE["status"] = result
            
            log_entry = f"Time: {index}s | AI: {result} (MSE: {score:.4f})"
            AI_STATE["logs"].append(log_entry)
            if len(AI_STATE["logs"]) > 10: 
                AI_STATE["logs"].pop(0)
            
            await asyncio.sleep(1.5)

    except Exception as e:
        logger.error(f"Error in simulation loop: {e}")
    
    AI_STATE["running"] = False
    AI_STATE["status"] = "NORMAL"
    AI_STATE["current_score"] = 0.0
    AI_STATE["logs"].append("System Standby.")

@router.post("/simulation/start")
def start_simulation(background_tasks: BackgroundTasks):
    if AI_STATE["running"]: 
        return {"status": "running", "message": "Simulation already running"}
    
    AI_STATE["running"] = True
    AI_STATE["logs"] = []
    AI_STATE["status"] = "NORMAL"
    AI_STATE["current_score"] = 0.0
    
    background_tasks.add_task(replay_traffic_loop)
    return {"status": "started", "message": "Traffic Replay STARTED"}

@router.post("/simulation/stop")
def stop_simulation():
    AI_STATE["running"] = False
    AI_STATE["status"] = "NORMAL"
    AI_STATE["current_score"] = 0.0
    AI_STATE["logs"].append("Stopped by User.")
    return {"status": "stopped", "message": "Stopping Simulation..."}

@router.get("/status")
def get_ai_status():
    return AI_STATE