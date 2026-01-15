from fastapi import APIRouter, BackgroundTasks
import asyncio
import numpy as np
import logging
from app.services.ai_service import ai_brain

# Setup Logger
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("AI-Loop")

router = APIRouter(tags=["AI Simulation"])

AI_STATE = {
    "running": False,
    "current_score": 0.0,
    "status": "NORMAL",
    "logs": []
}

def generate_demo_data():
    """
    Sinh dữ liệu giả lập trực tiếp trong RAM.
    Không cần đọc file CSV nữa -> Tránh lỗi file.
    """
    data = []
    
    # 1. 5 giây đầu: NORMAL (Traffic thấp)
    # [duration, protocol, src_bytes, dst_bytes, count]
    for _ in range(5):
        data.append([0.01, 1, 120, 240, 5])

    # 2. 20 giây giữa: ATTACK DDoS (Traffic cực lớn)
    for _ in range(20):
        data.append([5.5, 1, 9500, 8800, 500])

    # 3. 5 giây cuối: NORMAL (Hồi phục)
    for _ in range(5):
        data.append([0.02, 1, 110, 250, 4])
        
    return data

async def replay_traffic_loop():
    """Vòng lặp đọc dữ liệu từ RAM và giả lập traffic"""
    
    # Sinh dữ liệu mới mỗi khi chạy
    dataset = generate_demo_data()
    print(f"🚀 Starting Traffic Replay with {len(dataset)} samples...")

    try:
        for index, features in enumerate(dataset):
            # Kiểm tra cờ Stop từ người dùng
            if not AI_STATE["running"]: 
                print("🛑 Loop detected Stop signal. Breaking...")
                break
            
            # --- GỌI AI ENGINE ---
            result, score = ai_brain.predict_and_react(features)
            
            # --- CẬP NHẬT TRẠNG THÁI ---
            AI_STATE["current_score"] = float(score)
            AI_STATE["status"] = result
            
            log_entry = f"Time: {index}s | AI: {result} (MSE: {score:.4f})"
            
            # Lưu log (Giữ 10 dòng)
            AI_STATE["logs"].append(log_entry)
            if len(AI_STATE["logs"]) > 10: 
                AI_STATE["logs"].pop(0)
            
            print(log_entry) # Debug Terminal
            
            # Nghỉ 1.5s (Giả lập thời gian thực)
            await asyncio.sleep(1.5)

    except Exception as e:
        print(f"❌ Error in simulation loop: {e}")
    
    # --- KẾT THÚC VÒNG LẶP ---
    print("✅ Simulation Loop Finished.")
    
    # Reset trạng thái về Normal để giao diện xanh lại
    AI_STATE["running"] = False
    AI_STATE["status"] = "NORMAL"
    AI_STATE["current_score"] = 0.0
    AI_STATE["logs"].append("✅ System Standby.")

# --- API ENDPOINTS ---

@router.post("/simulation/start")
def start_simulation(background_tasks: BackgroundTasks):
    if AI_STATE["running"]: 
        return {"status": "running", "message": "Simulation already running"}
    
    print("🟢 API Start called.")
    AI_STATE["running"] = True
    AI_STATE["logs"] = []
    AI_STATE["status"] = "NORMAL"
    AI_STATE["current_score"] = 0.0
    
    background_tasks.add_task(replay_traffic_loop)
    return {"status": "started", "message": "Traffic Replay STARTED"}

@router.post("/simulation/stop")
def stop_simulation():
    print("🔴 API Stop called by Frontend.")
    AI_STATE["running"] = False
    # Reset ngay lập tức
    AI_STATE["status"] = "NORMAL"
    AI_STATE["current_score"] = 0.0
    AI_STATE["logs"].append("🛑 Stopped by User.")
    
    return {"status": "stopped", "message": "Stopping Simulation..."}

@router.get("/status")
def get_ai_status():
    return AI_STATE