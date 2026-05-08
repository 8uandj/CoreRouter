import csv
import os
import random
import numpy as np

# Tạo thư mục data nếu chưa có
os.makedirs(os.path.join(os.path.dirname(__file__), '..', '..', 'data'), exist_ok=True)
output_file = os.path.join(os.path.dirname(__file__), '..', '..', 'data', 'telecom_trace.csv')

NUM_SAMPLES = 2000

# Phân bổ xác suất
# 80% là luồng web/IoT thông thường nhẹ và ngắn
# 15% là Tải File / Game Server nặng vừa
# 5% là Tấn công DDoS hoặc Nghẽn rẽ nhánh (Yêu cầu khắt khe)
def generate_traffic():
    with open(output_file, mode='w', newline='') as file:
        writer = csv.writer(file)
        writer.writerow(['timestamp_sec', 'flow_id', 'cpu_req', 'ram_req', 'msd_req', 'is_ddos_spike'])
        
        for i in range(NUM_SAMPLES):
            rand_val = random.uniform(0, 1)
            
            if rand_val < 0.7:
                # Normal Traffic
                cpu = np.random.uniform(2.0, 10.0)
                ram = np.random.uniform(1.0, 5.0)
                msd = random.choice([1, 2])
                ddos = 0
            elif rand_val < 0.90:
                # Heavy Flow (Video Streaming / Big Data) - Bắt buộc đẩy qua lõi mạng (Core Node MSD=6)
                cpu = np.random.uniform(15.0, 30.0)
                ram = np.random.uniform(8.0, 20.0)
                msd = random.choice([4, 5])
                ddos = 0
            else:
                # SPIKE / DDoS / SFC cực nặng
                cpu = np.random.uniform(60.0, 95.0)
                ram = np.random.uniform(30.0, 50.0)
                msd = random.choice([4, 5])
                ddos = 1
                
            writer.writerow([round(i * 0.1, 2), f"FLOW_{i}", round(cpu, 2), round(ram, 2), msd, ddos])

if __name__ == "__main__":
    print(f"Bắt đầu sinh mô phỏng {NUM_SAMPLES} gói tin viễn thông...")
    generate_traffic()
    print(f"✅ Hoàn tất lưu dữ liệu tại: {output_file}")
