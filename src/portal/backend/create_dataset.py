import pandas as pd
import numpy as np

# Cấu hình
NORMAL_SAMPLES = 5
ATTACK_SAMPLES = 20
RECOVERY_SAMPLES = 5

data = []

# 1. Giai đoạn đầu: NORMAL (Traffic thấp, MSE sẽ thấp ~ 0.1 - 0.2)
# duration, protocol, src_bytes, dst_bytes, count, label
for i in range(NORMAL_SAMPLES):
    data.append([0.01, 1, 120, 240, 5, "normal"])

# 2. Giai đoạn giữa: ATTACK DDoS (Traffic khủng, MSE sẽ vọt lên > 0.8)
for i in range(ATTACK_SAMPLES):
    # Tăng src_bytes và count lên cực đại để AI nhận ra khác biệt
    data.append([5.5, 1, 9500, 8800, 500, "attack_ddos"])

# 3. Giai đoạn cuối: NORMAL (Hệ thống hồi phục)
for i in range(RECOVERY_SAMPLES):
    data.append([0.02, 1, 110, 250, 4, "normal"])

# Lưu file
columns = ["duration", "protocol", "src_bytes", "dst_bytes", "count", "label"]
df = pd.DataFrame(data, columns=columns)
df.to_csv("dataset.csv", index=False)

print(f"✅ Đã tạo dataset.csv với {len(df)} dòng dữ liệu.")
print("- 5 dòng đầu: Normal")
print("- 20 dòng giữa: Attack")
print("- 5 dòng cuối: Normal")



