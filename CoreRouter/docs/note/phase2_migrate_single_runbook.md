# Phase 2.2 — Single-VNF Make-Before-Break Runbook

Backend contract cho `vnf-migrate-single`. Bám đúng chuỗi MAKE → VERIFY → STEER → BREAK.

## 1. Hợp đồng API

| Bước   | Thành phần                          | Endpoint                                                       |
|--------|-------------------------------------|----------------------------------------------------------------|
| MAKE   | Backend → Tekton                    | `POST /api/orchestrate/migrate-single-vnf`                     |
| VERIFY | Backend đọc trạng thái PipelineRun  | `GET  /api/orchestrate/migrate-single-vnf/status?run=<run>`    |
| VERIFY | Backend đọc readiness + NodePort    | `GET  /api/orchestrate/migrate-single-vnf/endpoint?deploy=<n>` |
| STEER  | SDN/P4 controller (ngoài phạm vi)   | — không gọi backend ở bước này                                  |
| BREAK  | Backend → K8s (xoá VNF cũ)          | `POST /api/orchestrate/migrate-single-vnf/break`               |

> **Quan trọng:** Endpoint `migrate-single-vnf` chỉ thực hiện MAKE. KHÔNG xoá VNF cũ. KHÔNG steer traffic. BREAK bị chặn nếu caller chưa khẳng định steer thành công (`confirm_steer_done: true`).

## 2. Yêu cầu cluster (đã có sẵn)

- Namespace `core-router`.
- ConfigMap `vnf-inputs` chứa template manifest (vd `vnf-frr.yaml`).
- ServiceAccount `tekton-admin` đã được bind quyền apply/wait/get/delete.
- Pipeline `vnf-migrate-single` (xem `infrastructure/k8s/tekton/pipeline-migrate-single.yaml`).

Nếu Pipeline chưa tồn tại trong cluster:

```bash
kubectl apply -f infrastructure/k8s/tekton/pipeline-migrate-single.yaml
```

## 3. Local curl examples

Giả định backend chạy ở `http://localhost:8000`. VNF cũ là `vvoc-old`, replacement là `vvoc-mig-danang`, target location `dn`.

### 3.1. MAKE

```bash
curl -sS -X POST http://localhost:8000/api/orchestrate/migrate-single-vnf \
  -H 'Content-Type: application/json' \
  -d '{
        "oldDeployName": "vvoc-old",
        "newDeployName": "vvoc-mig-danang",
        "fileName": "vnf-frr.yaml",
        "targetLocation": "dn",
        "namespace": "core-router"
      }'
```

Kết quả mong đợi:

```json
{
  "status": "success",
  "message": "Migration MAKE pipeline started: mig-vvoc-mig-danang-xxxxxx. Old VNF kept; call break_old_vnf only after steer success.",
  "data": {
    "phase": "MAKE",
    "runName": "mig-vvoc-mig-danang-xxxxxx",
    "namespace": "core-router",
    "oldDeployName": "vvoc-old",
    "newDeployName": "vvoc-mig-danang"
  }
}
```

### 3.2. VERIFY — PipelineRun

```bash
curl -sS "http://localhost:8000/api/orchestrate/migrate-single-vnf/status?run=mig-vvoc-mig-danang-xxxxxx"
```

`data.overallStatus` sẽ chuyển từ `Running` → `Succeeded` khi `kubectl wait` xác nhận pod replacement Ready.

### 3.3. VERIFY — Endpoint NodePort

```bash
curl -sS "http://localhost:8000/api/orchestrate/migrate-single-vnf/endpoint?deploy=vvoc-mig-danang"
```

```json
{
  "status": "success",
  "data": {
    "deployName": "vvoc-mig-danang",
    "serviceName": "vvoc-mig-danang-svc",
    "ready": 1,
    "desired": 1,
    "isReady": true,
    "serviceType": "NodePort",
    "ports": [{"name": "vty", "port": 2601, "nodePort": 30xxx}]
  }
}
```

Cross-check bằng kubectl:

```bash
kubectl -n core-router get deploy vvoc-mig-danang
kubectl -n core-router get svc vvoc-mig-danang-svc -o wide
```

### 3.4. STEER (bên ngoài backend)

SDN/P4 controller cập nhật danh sách SID SRv6 ở Ingress để chỉ luồng sang replacement. Bước này dùng `POST /api/p4/rules` (đã có) hoặc CLI controller. Không gọi `migrate-single-vnf/break` ở đây.

### 3.5. BREAK (chỉ khi steer đã thành công)

```bash
curl -sS -X POST http://localhost:8000/api/orchestrate/migrate-single-vnf/break \
  -H 'Content-Type: application/json' \
  -d '{
        "oldDeployName": "vvoc-old",
        "namespace": "core-router",
        "confirm_steer_done": true
      }'
```

Nếu `confirm_steer_done` thiếu hoặc `false`, backend trả HTTP 409 với code `STEER_NOT_CONFIRMED`. Đây là lá chắn để tránh xoá nhầm VNF khi chưa bẻ luồng.

## 4. Bất biến (KHÔNG được vi phạm)

- Pipeline `vnf-migrate-single` PHẢI MAKE-only. Không thêm task `delete` hoặc `p4 rules` vào.
- Backend KHÔNG được tự gọi `break_old_vnf` từ trong handler `migrate-single-vnf`. Chỉ kích hoạt khi controller xác nhận steer.
- Không re-deploy toàn bộ SFC; chỉ thay từng VNF.
- HTTP 409 `NO_SAFE_ACTION` từ `/orchestrate` vẫn là Smart Admission Control — không sửa endpoint migrate để né.
