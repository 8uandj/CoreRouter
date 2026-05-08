# 3S-COM K8s Infrastructure Layer

Tầng Kubernetes/Tekton phục vụ Orchestrator của 3S-COM (3S = Smart, Scalable, Secure).
Mọi VNF được điều phối theo trục **Hybrid Orchestration (RuleDRL + MaskablePPO + Make-Before-Break)** đã thống nhất trong `.ai/1_context/architecture.md`.

## 1. Cấu trúc thư mục

```
infrastructure/k8s/
├── manifests/
│   ├── config-frr.yaml          # ConfigMap FRR (real, applyable)
│   ├── vvoc-app.yaml            # ConfigMap chứa source vvoc.py (real, applyable)
│   ├── vnf-inputs.yaml          # ConfigMap "vnf-inputs" — tổng hợp các template VNF (PLACEHOLDER_NAME)
│   ├── vnf-firewall.yaml        # Template VNF (PLACEHOLDER_NAME — KHÔNG apply trực tiếp)
│   ├── vnf-frr.yaml             # Template VNF (PLACEHOLDER_NAME — KHÔNG apply trực tiếp)
│   ├── vnf-idps.yaml            # Template VNF (PLACEHOLDER_NAME — KHÔNG apply trực tiếp)
│   ├── vnf-nat.yaml             # Template VNF (PLACEHOLDER_NAME — KHÔNG apply trực tiếp)
│   ├── vnf-lb.yaml              # Template VNF (PLACEHOLDER_NAME — KHÔNG apply trực tiếp)
│   └── vnf-voc.yaml             # Template VNF vVOC Option C (PLACEHOLDER_NAME — KHÔNG apply trực tiếp)
├── tekton/
│   ├── pipeline-vnf-fast.yaml         # vnf-lcm-fast: deploy 1 VNF
│   ├── pipeline-deploy-vnf.yaml
│   ├── pipeline-terminate-vnf.yaml
│   ├── pipeline-diagnostic.yaml
│   ├── pipeline-migrate-single-vnf.yaml  # Phase 2: Make-Before-Break (Make-only)
│   ├── pipelinerun-vnf-wide.yaml
│   └── tasks/
│       ├── task-prepare-vnf.yaml      # sed PLACEHOLDER_NAME → deployName
│       ├── task-kubectl-apply-file.yaml
│       ├── task-kubectl-wait.yaml
│       └── ...
├── ns-core-router.yaml
├── tekton-admin.yaml
├── kustomization.yaml
└── README.md
```

## 2. Hai loại file YAML — đừng nhầm lẫn

| Loại | Ví dụ | Có chứa `PLACEHOLDER_NAME`? | Apply trực tiếp được? |
|------|-------|------------------------------|------------------------|
| **Real** (ConfigMap, Namespace, RBAC, ServiceAccount) | `vnf-inputs.yaml`, `vvoc-app.yaml`, `config-frr.yaml`, `ns-core-router.yaml`, `tekton-admin.yaml` | Không (chuỗi `PLACEHOLDER_NAME` chỉ nằm bên trong `data:` của ConfigMap, là **dữ liệu**, không phải tên K8s object) | ✅ Có |
| **Template** (Deployment+Service VNF) | `vnf-firewall.yaml`, `vnf-frr.yaml`, `vnf-idps.yaml`, `vnf-nat.yaml`, `vnf-lb.yaml`, `vnf-voc.yaml` | ✅ Có (`metadata.name: PLACEHOLDER_NAME`) | ❌ Không — phải qua `prepare-vnf` thay tên trước |

### Lý do template KHÔNG nằm trong `kustomization.yaml`
File template còn chuỗi `PLACEHOLDER_NAME` ở `metadata.name`. Nếu thêm vào `kustomization.yaml` rồi `kubectl apply -k ...`, K8s sẽ tạo Deployment tên đúng là `PLACEHOLDER_NAME` (sai thiết kế) hoặc fail validation. Templates được Tekton/Backend gọi qua pipeline `vnf-lcm-fast` (xem mục 4).

## 3. Khởi tạo môi trường

```bash
kubectl apply -k infrastructure/k8s/
```

Lệnh này apply:
- Namespace `core-router`
- ServiceAccount `tekton-admin` + RBAC
- ConfigMap `frr-cfg` (cấu hình FRR)
- ConfigMap `vnf-inputs` (gồm 6 template VNF: firewall, frr, idps, nat, lb, voc)
- ConfigMap `vvoc-app` (source `vvoc.py` cho VNF vVOC Option C)
- Tất cả Tekton Tasks và Pipelines

> ⚠️ **Thứ tự apply quan trọng cho vVOC**: ConfigMap `vvoc-app` phải tồn tại **trước** khi pipeline `vnf-lcm-fast` deploy một instance `vnf-voc`, vì Deployment vVOC mount volume từ ConfigMap này. `kubectl apply -k` đảm bảo điều kiện này khi chạy 1 lần (kustomize gom các resource trong cùng request, K8s tự xử lý dependency theo eventual consistency); nếu apply tay thì apply `vvoc-app.yaml` trước.

## 4. Deploy 1 VNF (qua Tekton)

```bash
kubectl create -f infrastructure/k8s/tekton/pipelinerun-vnf-wide.yaml
```

Hoặc tạo `PipelineRun` ad-hoc cho NAT/LB/vVOC:

```yaml
apiVersion: tekton.dev/v1
kind: PipelineRun
metadata:
  generateName: vnf-nat-run-
  namespace: core-router
spec:
  pipelineRef: { name: vnf-lcm-fast }
  taskRunTemplate:
    serviceAccountName: tekton-admin
  workspaces:
  - name: ws
    volumeClaimTemplate:
      spec:
        accessModes: [ReadWriteOnce]
        resources: { requests: { storage: 50Mi } }
  params:
  - { name: ns,            value: core-router }
  - { name: deployName,    value: vnf-nat-001 }
  - { name: fileName,      value: vnf-nat.yaml }     # tên key trong ConfigMap vnf-inputs
  - { name: labelSelector, value: app=vnf-nat-001 }
  - { name: location,      value: hanoi-1 }
```

Backend `TektonOrchestrator.trigger_deploy(name, vnf_type, profile, location)` sẽ tự sinh `PipelineRun` tương đương (xem `src/infrastructure/k8s/tekton_orchestrator.py`).

> **NodePort Service** là milestone bridge Mininet ↔ K8s đầu tiên. Mọi VNF mới (NAT, LB, vVOC) đều expose `Service type: NodePort` để Mininet host có thể tới được pod thông qua node-IP của K8s worker.

## 5. Offline validation (không cần cluster)

### 5.1 YAML parse cho tất cả manifest
```bash
python3 - <<'PY'
import glob, sys, yaml
ok = True
for f in sorted(glob.glob("infrastructure/k8s/**/*.yaml", recursive=True)):
    try:
        list(yaml.safe_load_all(open(f)))
        print("OK   ", f)
    except Exception as e:
        ok = False
        print("FAIL ", f, "→", e)
sys.exit(0 if ok else 1)
PY
```

### 5.2 Kiểm tra template được render đúng (sed PLACEHOLDER_NAME)
Mô phỏng đúng hành vi của `prepare-vnf` (Tekton):

```bash
TARGET="vnf-voc.yaml"
DEPLOY_NAME="vnf-voc-smoke"
LOCATION="hanoi-1"

# 1. Trích đúng template từ ConfigMap (giả lập kubectl get cm vnf-inputs -o go-template)
python3 -c "
import yaml
d = yaml.safe_load(open('infrastructure/k8s/manifests/vnf-inputs.yaml'))
print(d['data']['$TARGET'])
" > /tmp/final.yaml

# 2. Thay PLACEHOLDER_NAME (giống prepare-vnf)
sed -i "s/PLACEHOLDER_NAME/$DEPLOY_NAME/g" /tmp/final.yaml

# 3. Chèn label location (giống prepare-vnf)
sed -i "0,/labels:/ s/labels:/labels:\n    core-router\/location: $LOCATION/" /tmp/final.yaml

# 4. Validate offline (không cần cluster)
kubectl --dry-run=client --validate=false apply -f /tmp/final.yaml
# hoặc:
python3 -c "import yaml; list(yaml.safe_load_all(open('/tmp/final.yaml'))); print('YAML OK')"
```

> ⚠️ **vVOC + sed**: file template `vnf-voc.yaml` chỉ tham chiếu ConfigMap `vvoc-app` qua `configMap.name: vvoc-app` (không chứa source Python). Do đó `prepare-vnf` chạy `sed s/PLACEHOLDER_NAME/.../g` không thể phá hỏng code Python. Đây là lý do source vVOC được tách thành file `vvoc-app.yaml` riêng.

### 5.3 Kustomize build (kiểm tra apply tổng)
```bash
kubectl kustomize infrastructure/k8s/ | head -n 60
# hoặc nếu có cluster:
kubectl --dry-run=client --validate=false apply -k infrastructure/k8s/
```

## 6. Tekton usage tương lai (khi đã có cluster MicroK8s/Kind)

1. `kubectl apply -k infrastructure/k8s/` (1 lần — RBAC, ConfigMap, Tekton Tasks, Pipelines)
2. Backend `/orchestrate` được gọi → `TektonOrchestrator.trigger_deploy(...)` sinh `PipelineRun`
3. Pipeline `vnf-lcm-fast` chạy:
   - `prepare-manifest` (Task `prepare-vnf`) — render template từ ConfigMap, sed `PLACEHOLDER_NAME`
   - `instantiate` — `kubectl apply -f /workspace/ws/final.yaml`
   - `wait-ready` — `kubectl rollout status deploy -l app=<name> --timeout=180s`
   - `observe` — `kubectl get pods -l ...`
4. Khi Bi-GRU bật `Alert=1` cho node hosting VNF, Backend gọi pipeline `vnf-migrate-single` (Phase 2, xem `tekton/pipeline-migrate-single-vnf.yaml`) để **Make** bản sao tại node đích — KHÔNG xóa VNF cũ trước khi Steer xong.

## 7. Smart Admission Control — không phải bug

HTTP `409 NO_SAFE_ACTION` từ `/orchestrate` là hành vi đúng theo Định lý Little (Little's Law): khi không tồn tại cặp `[v_place, v_route]` thoả mọi Hard Constraint (MSD ≤ giới hạn của switch Tofino, CPU/RAM, Alert Flag), hệ thống **PHẢI từ chối** request thay vì ép placement vào node nguy hiểm. Tuyệt đối không "fix" bằng cách bỏ Action Masking, hạ MSD, hay ép node.
