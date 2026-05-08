# Runbook — `vnf-migrate-single` (Make-Before-Break, Make step)

Pipeline `tekton/pipeline-migrate-single-vnf.yaml` thực hiện **bước MAKE** trong quy trình Make-Before-Break để di dời 1 VNF sang node đích, mà KHÔNG bẻ lái traffic và KHÔNG xóa VNF cũ.

## 1. Trách nhiệm rõ ràng

| Bước Make-Before-Break | Ai làm                              | Trong pipeline này? |
|-------------------------|-------------------------------------|---------------------|
| **Make** (tạo replacement Ready) | Tekton — `vnf-migrate-single`       | ✅ |
| **Steer** (rewrite luật SRv6 / NodePort) | Backend `/orchestrate` + SDN Controller | ❌ (ngoài pipeline) |
| **Break** (xóa VNF cũ)            | Backend gọi pipeline `vnf-terminate` SAU khi Steer thành công | ❌ (pipeline `vnf-terminate` riêng) |

> ⛔ **Tuyệt đối KHÔNG** thêm bước `kubectl delete deploy <oldDeployName>` vào pipeline `vnf-migrate-single`. Việc xóa phải xảy ra **sau khi controller xác nhận traffic đã switch**, nếu không sẽ phá Zero-Downtime SLA.

## 2. Tham số

| Param | Bắt buộc | Ví dụ | Ý nghĩa |
|-------|----------|-------|---------|
| `ns` | (default `core-router`) | `core-router` | namespace |
| `oldDeployName` | ✅ | `vnf-frr-001` | Tên VNF cũ — chỉ dùng để log + emit `result.oldDeployName` cho Backend gọi `vnf-terminate` sau Steer |
| `newDeployName` | ✅ | `vnf-frr-001-mig-hanoi2` | Tên replacement (KHÔNG trùng oldDeployName) |
| `fileName` | ✅ | `vnf-frr.yaml` | Key trong ConfigMap `vnf-inputs` |
| `targetLocation` | (default `auto`) | `hanoi-2` | Gán label `core-router/location` để DRL quan sát |

## 3. PipelineRun mẫu (tay)

```yaml
apiVersion: tekton.dev/v1
kind: PipelineRun
metadata:
  generateName: vnf-migrate-
  namespace: core-router
spec:
  pipelineRef: { name: vnf-migrate-single }
  taskRunTemplate: { serviceAccountName: tekton-admin }
  workspaces:
  - name: ws
    volumeClaimTemplate:
      spec:
        accessModes: [ReadWriteOnce]
        resources: { requests: { storage: 50Mi } }
  params:
  - { name: oldDeployName,  value: vnf-frr-001 }
  - { name: newDeployName,  value: vnf-frr-001-mig-hanoi2 }
  - { name: fileName,       value: vnf-frr.yaml }
  - { name: targetLocation, value: hanoi-2 }
```

## 4. Backend nên gọi như thế nào (Phase 2 sắp tới)

`src/infrastructure/k8s/tekton_orchestrator.py` sẽ thêm method:

```python
def trigger_migrate_single(
    self,
    old_deploy_name: str,
    new_deploy_name: str,
    vnf_type: str,
    target_location: str,
) -> Dict[str, Any]:
    """Trigger the MAKE step of Make-Before-Break for a single VNF."""
    template_file = {
        "firewall": "vnf-firewall.yaml",
        "idps":     "vnf-idps.yaml",
        "router":   "vnf-frr.yaml",
        "nat":      "vnf-nat.yaml",
        "lb":       "vnf-lb.yaml",
        "voc":      "vnf-voc.yaml",
    }.get(vnf_type, "vnf-frr.yaml")

    run_name = f"migrate-{vnf_type}-{uuid.uuid4().hex[:6]}"
    pipeline_run = {
        "apiVersion": "tekton.dev/v1",
        "kind": "PipelineRun",
        "metadata": {"name": run_name},
        "spec": {
            "pipelineRef": {"name": "vnf-migrate-single"},
            "taskRunTemplate": {"serviceAccountName": "tekton-admin"},
            "params": [
                {"name": "ns",             "value": "core-router"},
                {"name": "oldDeployName",  "value": old_deploy_name},
                {"name": "newDeployName",  "value": new_deploy_name},
                {"name": "fileName",       "value": template_file},
                {"name": "targetLocation", "value": target_location},
            ],
            "workspaces": [{
                "name": "ws",
                "volumeClaimTemplate": {
                    "spec": {
                        "accessModes": ["ReadWriteOnce"],
                        "resources": {"requests": {"storage": "50Mi"}},
                    }
                },
            }],
        },
    }
    # ... self.custom_api.create_namespaced_custom_object(...)
```

Sau khi pipeline `Succeeded`:
1. Backend đọc `result.newDeployName`, query Service `<newDeployName>-svc` (NodePort) lấy `nodePort`.
2. Gọi SDN Controller: rewrite luật SRv6 / iptables ở Ingress để bẻ luồng sang replacement (Switching Cost = -3.0).
3. Sau khi monitor xác nhận traffic ổn định trên replacement (vd quan sát >5s không drop, hoặc state_manager báo OK), gọi `trigger_terminate(old_deploy_name)` → pipeline `vnf-terminate` xóa VNF cũ.

## 5. Test pipeline khi đã có cluster

```bash
# 1. Cluster + manifests sẵn sàng
kubectl apply -k infrastructure/k8s/

# 2. Deploy 1 VNF "cũ"
cat <<'EOF' | kubectl create -f -
apiVersion: tekton.dev/v1
kind: PipelineRun
metadata: { generateName: deploy-frr-old-, namespace: core-router }
spec:
  pipelineRef: { name: vnf-lcm-fast }
  taskRunTemplate: { serviceAccountName: tekton-admin }
  workspaces:
  - name: ws
    volumeClaimTemplate:
      spec:
        accessModes: [ReadWriteOnce]
        resources: { requests: { storage: 50Mi } }
  params:
  - { name: ns, value: core-router }
  - { name: deployName, value: vnf-frr-001 }
  - { name: fileName,   value: vnf-frr.yaml }
  - { name: labelSelector, value: app=vnf-frr-001 }
  - { name: location,   value: hanoi-1 }
EOF

# 3. Migrate sang hanoi-2 (Make only)
cat <<'EOF' | kubectl create -f -
apiVersion: tekton.dev/v1
kind: PipelineRun
metadata: { generateName: migrate-frr-, namespace: core-router }
spec:
  pipelineRef: { name: vnf-migrate-single }
  taskRunTemplate: { serviceAccountName: tekton-admin }
  workspaces:
  - name: ws
    volumeClaimTemplate:
      spec:
        accessModes: [ReadWriteOnce]
        resources: { requests: { storage: 50Mi } }
  params:
  - { name: oldDeployName,  value: vnf-frr-001 }
  - { name: newDeployName,  value: vnf-frr-001-mig-hanoi2 }
  - { name: fileName,       value: vnf-frr.yaml }
  - { name: targetLocation, value: hanoi-2 }
EOF

# 4. Quan sát: cả VNF cũ và replacement cùng tồn tại
kubectl -n core-router get deploy -l 'core-router/role'
# kỳ vọng: vnf-frr-001 (location=hanoi-1) Ready 1/1
#          vnf-frr-001-mig-hanoi2 (location=hanoi-2) Ready 1/1

# 5. (Sau khi Backend Steer xong) — Break thủ công
cat <<'EOF' | kubectl create -f -
apiVersion: tekton.dev/v1
kind: PipelineRun
metadata: { generateName: terminate-frr-old-, namespace: core-router }
spec:
  pipelineRef: { name: vnf-terminate }
  taskRunTemplate: { serviceAccountName: tekton-admin }
  params:
  - { name: deployName, value: vnf-frr-001 }
EOF
```

## 6. Smart Admission Control reminder

Khi DRL trả về HTTP `409 NO_SAFE_ACTION` (không có node nào đáp MSD/CPU/Alert), Backend KHÔNG được fallback sang gọi `vnf-migrate-single` rồi "thử đại" — đây là hành vi đúng theo Định lý Little (xem `.ai/2_rules/conventions.md` mục 6 và `.ai/1_context/current_state.md` mục 3). Migrate chỉ kích hoạt khi đã có node đích an toàn (`Alert=0`, `MSD_used + len(srv6_sids) ≤ msd_limit`).
