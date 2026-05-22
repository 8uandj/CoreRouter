#!/bin/bash
# =============================================================================
# 3S-COM Testbed — All-in-One Setup Script
# =============================================================================
# Dùng để dựng lại toàn bộ testbed trên một server Ubuntu mới.
#
# PREREQUISITE:
#   1. Server Ubuntu 20.04/22.04, kết nối internet
#   2. Đã clone/pull project về thư mục hiện tại:
#        git clone <repo_url> . && cd CoreRouter
#   3. Chạy với user có quyền sudo (không phải root):
#        bash setup_testbed.sh
#
# Sau khi xong, kiểm tra bằng:
#   ./test/test_phases.sh   → phải đạt 24/24 PASS
# =============================================================================

set -e
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# ── Colors ──────────────────────────────────────────────────────────────────
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
CYAN='\033[0;36m'; BOLD='\033[1m'; RESET='\033[0m'
info()    { echo -e "${CYAN}[INFO]${RESET} $*"; }
success() { echo -e "${GREEN}[✅ OK]${RESET} $*"; }
warn()    { echo -e "${YELLOW}[⚠️  WARN]${RESET} $*"; }
error()   { echo -e "${RED}[❌ ERROR]${RESET} $*"; exit 1; }
header()  { echo -e "\n${BOLD}══════════════════════════════════════════════${RESET}"; \
             echo -e "${BOLD}  $*${RESET}"; \
             echo -e "${BOLD}══════════════════════════════════════════════${RESET}"; }

# ── Config ───────────────────────────────────────────────────────────────────
NAMESPACE="core-router"
REGISTRY="localhost:32000"
VENV_DIR="$SCRIPT_DIR/venv"
FRONTEND_DIR="$SCRIPT_DIR/src/portal/frontend"
BACKEND_DOCKERFILE="$SCRIPT_DIR/src/portal/backend/Dockerfile.py311"

IMAGES=(
  "alpine:latest"
  "quay.io/frrouting/frr:9.1.1"
  "nginx:1.27-alpine"
  "python:3.11-alpine"
  "bitnami/kubectl:latest"
  "p4lang/behavioral-model:latest"
)
REGISTRY_TAGS=(
  "localhost:32000/alpine:latest"
  "localhost:32000/frr:9.1.1"
  "localhost:32000/nginx:1.27-alpine"
  "localhost:32000/python:3.11-alpine"
  "localhost:32000/kubectl:1.30"
  "localhost:32000/bmv2:latest"
)

# =============================================================================
# PHASE 0 — System Prerequisites
# =============================================================================
header "PHASE 0 — Installing System Prerequisites"

info "Updating apt..."
sudo apt-get update -qq

info "Installing base packages..."
sudo apt-get install -y --no-install-recommends \
  curl git python3 python3-pip python3-venv \
  mininet ovs-common openvswitch-switch \
  iproute2 iptables net-tools \
  make build-essential

# Docker
if ! command -v docker &>/dev/null; then
  info "Installing Docker..."
  curl -fsSL https://get.docker.com | sudo sh
  sudo usermod -aG docker "$USER"
  warn "Docker installed. Bạn cần re-login để dùng Docker không cần sudo."
  warn "Tạm thời script tiếp tục dùng 'sudo docker'."
  DOCKER_CMD="sudo docker"
else
  DOCKER_CMD="docker"
  success "Docker already installed"
fi

# Node.js / npm
if ! command -v npm &>/dev/null; then
  info "Installing Node.js 20..."
  curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -
  sudo apt-get install -y nodejs
fi
success "Node.js $(node --version) / npm $(npm --version)"

# MicroK8s
if ! command -v microk8s &>/dev/null; then
  info "Installing MicroK8s..."
  sudo snap install microk8s --classic
  sudo usermod -aG microk8s "$USER"
  sudo chown -R "$USER:$USER" ~/.kube 2>/dev/null || true
  warn "MicroK8s installed. Bạn có thể cần re-login để dùng không cần sudo."
fi

info "Waiting for MicroK8s to be ready (up to 3 minutes)..."
sudo microk8s status --wait-ready --timeout 180 || error "MicroK8s not ready after 3 minutes"
success "MicroK8s ready"

# =============================================================================
# PHASE 1 — MicroK8s Addons & Tekton
# =============================================================================
header "PHASE 1 — Enabling MicroK8s Addons"

for addon in registry dns storage; do
  if sudo microk8s status | grep -q "  $addon: enabled"; then
    success "Addon '$addon' already enabled"
  else
    info "Enabling addon: $addon..."
    sudo microk8s enable "$addon"
  fi
done

# Tekton (community addon hoặc kubectl apply)
if ! sudo microk8s kubectl get crd pipelines.tekton.dev &>/dev/null 2>&1; then
  info "Installing Tekton Pipelines..."
  sudo microk8s kubectl apply -f \
    https://storage.googleapis.com/tekton-releases/pipeline/latest/release.yaml
  info "Waiting for Tekton to be ready..."
  sleep 30
  sudo microk8s kubectl wait --for=condition=ready pod \
    -n tekton-pipelines --all --timeout=180s || warn "Some Tekton pods may still be starting"
else
  success "Tekton already installed"
fi

# =============================================================================
# PHASE 2 — Docker Images → MicroK8s Local Registry
# =============================================================================
header "PHASE 2 — Pulling Docker Images & Importing to MicroK8s"

info "Waiting for MicroK8s registry to be ready..."
for i in $(seq 1 20); do
  if curl -s http://$REGISTRY/v2/ &>/dev/null; then break; fi
  sleep 5
done

for i in "${!IMAGES[@]}"; do
  SRC="${IMAGES[$i]}"
  DST="${REGISTRY_TAGS[$i]}"

  info "Pulling $SRC..."
  $DOCKER_CMD pull "$SRC"

  info "Importing $SRC → MicroK8s containerd..."
  $DOCKER_CMD save "$SRC" | sudo microk8s ctr image import -

  # Tag đặc biệt cho kubectl
  if [[ "$SRC" == "bitnami/kubectl:latest" ]]; then
    sudo microk8s ctr image tag "docker.io/bitnami/kubectl:latest" "$DST" 2>/dev/null || true
  elif [[ "$SRC" == "alpine:latest" ]]; then
    sudo microk8s ctr image tag "docker.io/library/alpine:latest" "$DST" 2>/dev/null || true
  elif [[ "$SRC" == "nginx:1.27-alpine" ]]; then
    sudo microk8s ctr image tag "docker.io/library/nginx:1.27-alpine" "$DST" 2>/dev/null || true
  elif [[ "$SRC" == "python:3.11-alpine" ]]; then
    sudo microk8s ctr image tag "docker.io/library/python:3.11-alpine" "$DST" 2>/dev/null || true
  elif [[ "$SRC" == "quay.io/frrouting/frr:9.1.1" ]]; then
    sudo microk8s ctr image tag "quay.io/frrouting/frr:9.1.1" "$DST" 2>/dev/null || true
  elif [[ "$SRC" == "p4lang/behavioral-model:latest" ]]; then
    sudo microk8s ctr image tag "docker.io/p4lang/behavioral-model:latest" "$DST" 2>/dev/null || true
  fi

  info "Pushing $DST to local registry..."
  sudo microk8s ctr image push "$DST" 2>/dev/null || warn "Push skipped (may already exist)"
  success "$SRC → $DST"
done

# =============================================================================
# PHASE 3 — Deploy K8s Resources & Tekton Pipelines
# =============================================================================
header "PHASE 3 — Deploying K8s Resources (Namespace, RBAC, Tekton)"

info "Applying K8s manifests (kustomize)..."
sudo microk8s kubectl apply -k infrastructure/k8s/

info "Waiting for resources to be ready..."
sleep 10
sudo microk8s kubectl wait --for=condition=ready pod \
  -n "$NAMESPACE" --all --timeout=120s 2>/dev/null || true

info "Applying vVOC Phase 3 test deployment..."
sudo microk8s kubectl apply -f infrastructure/k8s/manifests/vvoc-phase3-test.yaml
sudo microk8s kubectl rollout status deploy/vnf-voc-phase3 -n "$NAMESPACE" --timeout=120s

success "K8s resources deployed"

# =============================================================================
# PHASE 4 — Mininet Bridge Setup
# =============================================================================
header "PHASE 4 — Setting Up Mininet ↔ K8s Bridge"

info "Running bridge setup for transparent routing..."
if [[ -f "infrastructure/sdn/bridge_k8s.sh" ]]; then
  sudo bash infrastructure/sdn/bridge_k8s.sh || warn "Bridge setup failed (may need Mininet running first)"
else
  warn "bridge_k8s.sh not found — skipping. Run manually after starting Mininet."
fi

# =============================================================================
# PHASE 5 — Compile P4 Program
# =============================================================================
header "PHASE 5 — Compiling P4 SRv6 Program"

if command -v p4c &>/dev/null; then
  info "Compiling P4 program..."
  cd "$SCRIPT_DIR/infrastructure/sdn/p4" && make all && cd "$SCRIPT_DIR"
  success "P4 compilation done"
else
  warn "p4c not found — P4 compilation skipped."
  warn "Để compile P4: sudo apt install p4lang-p4c, sau đó cd infrastructure/sdn/p4 && make all"
  if [[ -f "infrastructure/sdn/p4/srv6_basic.json" ]]; then
    success "Pre-compiled P4 JSON found — Phase 4 can still run"
  fi
fi

# =============================================================================
# PHASE 6 — Python Virtual Environment
# =============================================================================
header "PHASE 6 — Setting Up Python venv (for Mininet/scripts)"

if [[ ! -d "$VENV_DIR" ]]; then
  info "Creating Python venv..."
  python3 -m venv "$VENV_DIR"
fi

info "Installing Python dependencies..."
"$VENV_DIR/bin/pip" install --upgrade pip -q
"$VENV_DIR/bin/pip" install \
  kubernetes requests flask \
  mininet 2>/dev/null || true

# AI/ML deps (optional — cho training scripts local)
if [[ -f requirements.txt ]]; then
  "$VENV_DIR/bin/pip" install -r requirements.txt -q 2>/dev/null || \
    warn "Một số ML packages cài thất bại (bình thường nếu không có GPU/CUDA)"
fi
success "Python venv ready at $VENV_DIR"

# =============================================================================
# PHASE 7 — Frontend
# =============================================================================
header "PHASE 7 — Installing Frontend Dependencies"

if [[ -d "$FRONTEND_DIR" ]]; then
  info "Running npm install..."
  cd "$FRONTEND_DIR" && npm install --silent && cd "$SCRIPT_DIR"
  success "Frontend deps installed"
else
  warn "Frontend directory not found at $FRONTEND_DIR"
fi

# =============================================================================
# PHASE 8 — Build Backend Docker (Python 3.11 + Real AI Model)
# =============================================================================
header "PHASE 8 — Building Backend Docker Image (Python 3.11)"

if [[ -f "$BACKEND_DOCKERFILE" ]]; then
  info "Building 3s-com-backend:py311 image (5–10 phút)..."
  $DOCKER_CMD build \
    -f "$BACKEND_DOCKERFILE" \
    -t "3s-com-backend:py311" \
    "$SCRIPT_DIR"
  success "Backend Docker image built"
else
  warn "Dockerfile.py311 not found — skip Docker build"
fi

# =============================================================================
# PHASE 9 — Verification
# =============================================================================
header "PHASE 9 — Running Testbed Verification"

info "Running test_phases.sh..."
if [[ -f "test/test_phases.sh" ]]; then
  bash test/test_phases.sh
else
  warn "test/test_phases.sh not found"
fi

# =============================================================================
# DONE
# =============================================================================
echo ""
echo -e "${GREEN}${BOLD}"
echo "╔══════════════════════════════════════════════════════╗"
echo "║         3S-COM TESTBED SETUP COMPLETE! 🎉            ║"
echo "╚══════════════════════════════════════════════════════╝"
echo -e "${RESET}"
echo -e "${BOLD}Cách chạy hệ thống:${RESET}"
echo ""
echo "  # 1. Backend (Python 3.11 + Real AI Model)"
echo "  ./run_backend_docker.sh run"
echo ""
echo "  # 2. Frontend"
echo "  cd src/portal/frontend && npm run dev"
echo ""
echo "  # 3. Mininet + P4 (cần terminal riêng, chạy với sudo)"
echo "  sudo $VENV_DIR/bin/python3 infrastructure/sdn/topo_p4.py"
echo ""
echo "  # 4. SDN Controller (cần terminal riêng)"
echo "  $VENV_DIR/bin/python3 infrastructure/sdn/controller.py"
echo ""
echo -e "${CYAN}Kiểm tra log backend: ./run_backend_docker.sh logs${RESET}"
echo ""
