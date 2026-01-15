from app.core.k8s_client import k8s, logger

def get_topology():
    if not k8s.core_api:
        return {"nodes": [], "edges": []}
    
    try:
        pods = k8s.core_api.list_namespaced_pod(namespace="vnf")
        nodes = []
        edges = []
        
        # 1. CHUẨN BỊ DỮ LIỆU
        raw_nodes = []
        for pod in pods.items:
            # Chỉ lấy Pod đang chạy hoặc đang tạo, bỏ qua Pod chết
            if pod.status.phase in ["Succeeded", "Failed"]: continue
            
            name = pod.metadata.name
            
            # Logic xác định Role (Vai trò)
            role = 'router' # Mặc định
            if 'firewall' in name or 'fw' in name: role = 'firewall'
            elif 'idps' in name: role = 'idps'
            else: role = pod.metadata.labels.get('role', 'router')

            raw_nodes.append({
                "id": name, "role": role,
                "ip": pod.status.pod_ip, "status": pod.status.phase
            })

        # 2. TÍNH TOÁN VỊ TRÍ (SMART COMPACT GRID)
        # [CẬP NHẬT] Thu hẹp khoảng cách tối đa để chúng xít lại gần nhau
        X_GAP = 200  # Khoảng cách ngang (giữa các cột)
        Y_GAP = 90   # Khoảng cách dọc (giữa các hàng)
        START_X = 50
        START_Y = 50

        role_x_index = {"firewall": 0, "idps": 1, "router": 2}
        y_counters = {"firewall": 0, "idps": 0, "router": 0}

        # Sắp xếp tên để vị trí ổn định, không bị nhảy lung tung khi refresh
        raw_nodes.sort(key=lambda x: x['id']) 

        for n in raw_nodes:
            role = n["role"]
            col_idx = role_x_index.get(role, 2)
            
            # Tính tọa độ
            x_pos = START_X + (col_idx * X_GAP)
            y_pos = START_Y + (y_counters[role] * Y_GAP)
            y_counters[role] += 1

            nodes.append({
                "id": n["id"],
                "type": "customNode", # Đảm bảo Frontend có component này
                "data": { 
                    "label": n["id"], 
                    "ip": n["ip"],
                    "role": role, 
                    "status": n["status"]
                },
                "position": {"x": x_pos, "y": y_pos},
                "draggable": True
            })

        # 3. VẼ DÂY (EDGES)
        fw_ids = [n["id"] for n in nodes if n["data"]["role"] == "firewall"]
        idps_ids = [n["id"] for n in nodes if n["data"]["role"] == "idps"]
        r_ids = [n["id"] for n in nodes if n["data"]["role"] == "router"]

        # 3.1 Firewall -> IDPS (Xanh Dương - Traffic lọc)
        for fw in fw_ids:
            for idps in idps_ids:
                edges.append({
                    "id": f"e-{fw}-{idps}",
                    "source": fw, "target": idps,
                    "animated": True, "style": {"stroke": "#06b6d4", "strokeWidth": 2}
                })

        # 3.2 IDPS -> Router (Xanh Lá - Traffic sạch)
        for idps in idps_ids:
            for r in r_ids:
                edges.append({
                    "id": f"e-{idps}-{r}",
                    "source": idps, "target": r,
                    "animated": True, "style": {"stroke": "#10b981", "strokeWidth": 2}
                })

        # 3.3 Firewall -> Router (Tím Nét Đứt - Bypass/Direct Link)
        # [CẬP NHẬT] Luôn vẽ dây này để đảm bảo logic kết nối
        for fw in fw_ids:
            for r in r_ids:
                edges.append({
                    "id": f"e-bypass-{fw}-{r}",
                    "source": fw, "target": r,
                    "animated": True, 
                    "style": {
                        "stroke": "#8b5cf6", # Tím (Violet)
                        "strokeWidth": 1.5, 
                        "strokeDasharray": "5,5", # Nét đứt
                        "opacity": 0.5 # Hơi mờ để không rối mắt
                    }
                })
        
        # [Trường hợp phụ] Nếu không có IDPS, vẽ dây Firewall -> Router là nét liền (Xanh lá)
        # Để thể hiện traffic chính đi thẳng qua
        if not idps_ids:
             for fw in fw_ids:
                for r in r_ids:
                    # Kiểm tra xem đã có dây tím chưa, nếu có thì vẽ đè lên hoặc thay thế logic
                    # Ở đây ta vẽ thêm dây xanh lá tượng trưng cho Main Traffic
                    edges.append({
                        "id": f"e-main-{fw}-{r}",
                        "source": fw, "target": r,
                        "animated": True, 
                        "style": {"stroke": "#10b981", "strokeWidth": 2}
                    })

        return {"nodes": nodes, "edges": edges}
    except Exception as e:
        logger.error(f"Error building topology: {e}")
        return {"nodes": [], "edges": []}