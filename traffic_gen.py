import time
import requests
import subprocess
import os
from scapy.all import IP, UDP, send
import sys

BACKEND_URL = "http://localhost:8000/api"
TARGET_IP = "10.0.0.2" # Mock target IP for demo (Host HCM)

def pump_elephant_flow_iperf3(duration=30):
    """
    RÀ SOÁT 3: Dùng iperf3 để có TCP State Machine hoàn chỉnh.
    Đảm bảo các VNF Stateful không drop gói tin.
    """
    print(f"[*] Starting Stateful Elephant flow (iperf3) to {TARGET_IP}...")
    try:
        # Chạy iperf3 client trong background
        cmd = ["iperf3", "-c", TARGET_IP, "-t", str(duration), "-P", "1"]
        process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        print("[+] iperf3 session started. Monitoring for 'Connection reset'...")
        return process
    except FileNotFoundError:
        print("[!] iperf3 not found. Please install it: sudo apt install iperf3")
        return None

def simulate_ddos_udp_flood(duration=10):
    """
    Dùng Scapy để bơm UDP rác (Stateless) giả lập DDoS/Attack flow.
    """
    print(f"[*] Starting UDP Flood (DDoS simulation) to {TARGET_IP}...")
    start_time = time.time()
    count = 0
    while time.time() - start_time < duration:
        pkt = IP(dst=TARGET_IP)/UDP(sport=5678, dport=80)/("ATTACK" * 128)
        send(pkt, verbose=False)
        count += 1
        if count % 500 == 0:
            print(f"[+] Sent {count} UDP attack packets...")
    print(f"[*] DDoS Simulation finished. Total UDP: {count}")

def trigger_alert(enable=True):
    """
    Call Backend API to simulate Bi-GRU DDoS alert.
    """
    print(f"\n[*] Triggering Alert={enable} via API...")
    try:
        resp = requests.post(f"{BACKEND_URL}/orchestrate/alert?alert={str(enable).lower()}")
        if resp.status_code == 200:
            print(f"[+] API Success: Alert set to {enable}")
        else:
            print(f"[!] API Error: {resp.status_code}")
    except Exception as e:
        print(f"[!] Connection failed: {e}")

def request_orchestration():
    """
    Request a new orchestration decision.
    """
    print("[*] Requesting Hybrid Orchestration...")
    payload = {
        "flow_id": "demo-flow-mbb",
        "cpu_req": 25.0,
        "ram_req": 15.0,
        "msd_req": 3,
        "service_type": "Data",
        "alert_flag": True,
        "source_node": "Hanoi",
        "destination_node": "HoChiMinh"
    }
    try:
        resp = requests.post(f"{BACKEND_URL}/orchestrate", json=payload)
        if resp.status_code == 200:
            data = resp.json()
            print(f"[+] Response: Method={data['method_used']}, MBB={data['make_before_break']}")
            return data
        else:
            print(f"[!] API Error: {resp.status_code} - {resp.text}")
    except Exception as e:
        print(f"[!] Connection failed: {e}")
    return None

if __name__ == "__main__":
    if os.geteuid() != 0:
        print("!!! WARNING: Scapy requires root privileges. Please run with 'sudo python3 traffic_gen.py' !!!")
        # sys.exit(1) # Don't exit yet, maybe iperf3 works

    print("=== 3S-COM Phase 5 Demo: Zero-Downtime Verification ===")
    
    # 1. Start iperf3 (Elephant Flow)
    iperf_proc = pump_elephant_flow_iperf3(duration=40)
    time.sleep(2)

    # 2. Trigger DDoS Alert
    trigger_alert(True)
    
    # 3. Request Orchestration (Trigger MBB)
    print("\n--- STEP: Requesting Migration ---")
    request_orchestration()
    
    # 4. Inject UDP Flood while migrating
    simulate_ddos_udp_flood(duration=15)
    
    # 5. Clear Alert
    trigger_alert(False)
    
    if iperf_proc:
        iperf_proc.wait()
        print("\n--- iperf3 Final Result ---")
        out, err = iperf_proc.communicate()
        print(out.decode())

    print("\n=== Demo Script Finished ===")
