#!/bin/bash
# =============================================================================
# join_worker_node.sh — Tự động join k8s-master vào MicroK8s cluster
# =============================================================================
# Chạy script này TRÊN SERVER k8s-master (Oracle Linux / RHEL-based)
#
# Usage:
#   bash join_worker_node.sh
# Hoặc truyền join URL tùy chỉnh:
#   bash join_worker_node.sh "10.10.6.231:25000/<token>"
#
# NOTE: Join token hết hạn sau ~24h. Nếu hết hạn, chạy lại trên 3S-COM:
#   sudo microk8s add-node
# Rồi copy token mới vào đây.
# =============================================================================

set -e

# ── Config ───────────────────────────────────────────────────────────────────
# Dùng IP nội bộ để 2 server giao tiếp (10.10.6.x là mạng chung)
JOIN_URL="${1:-10.10.6.231:25000/70d01b84de06a9803fcc94f6798c935e/7e3107137d6c}"
MASTER_IP="10.10.6.231"

# ── Colors ───────────────────────────────────────────────────────────────────
GREEN='\033[0;32m'; CYAN='\033[0;36m'; YELLOW='\033[1;33m'
RED='\033[0;31m'; BOLD='\033[1m'; RESET='\033[0m'
info()    { echo -e "${CYAN}[INFO]${RESET} $*"; }
success() { echo -e "${GREEN}[✅]${RESET} $*"; }
warn()    { echo -e "${YELLOW}[⚠️]${RESET} $*"; }
error()   { echo -e "${RED}[❌]${RESET} $*"; exit 1; }

echo -e "${BOLD}"
echo "╔══════════════════════════════════════════════════════╗"
echo "║   3S-COM — Join Worker Node to MicroK8s Cluster      ║"
echo "╚══════════════════════════════════════════════════════╝"
echo -e "${RESET}"
info "Master: $MASTER_IP"
info "Join URL: $JOIN_URL"
echo ""

# ── Kiểm tra kết nối đến master ──────────────────────────────────────────────
info "Kiểm tra kết nối đến master ($MASTER_IP)..."
if ! ping -c 2 -W 3 "$MASTER_IP" &>/dev/null; then
    error "Không ping được $MASTER_IP. Kiểm tra lại network."
fi
success "Kết nối đến master OK"

# ── Detect OS ────────────────────────────────────────────────────────────────
OS_ID=$(cat /etc/os-release | grep "^ID=" | cut -d= -f2 | tr -d '"')
info "Detected OS: $OS_ID"

# ── Cài snapd (nếu chưa có) — Oracle Linux / RHEL dùng dnf ──────────────────
install_snapd_rhel() {
    info "Cài snapd trên Oracle Linux/RHEL..."
    sudo dnf install -y epel-release 2>/dev/null || \
        sudo dnf install -y https://dl.fedoraproject.org/pub/epel/epel-release-latest-$(rpm -E %rhel).noarch.rpm
    sudo dnf install -y snapd
    sudo systemctl enable --now snapd.socket
    # Symlink cần thiết cho snap
    if [[ ! -L /snap ]]; then
        sudo ln -sf /var/lib/snapd/snap /snap
    fi
    info "Chờ snapd khởi động (15s)..."
    sleep 15
    success "snapd installed"
}

install_snapd_ubuntu() {
    info "Cài snapd trên Ubuntu..."
    sudo apt-get update -qq
    sudo apt-get install -y snapd
    success "snapd installed"
}

if ! command -v snap &>/dev/null; then
    case "$OS_ID" in
        ol|rhel|centos|fedora|almalinux|rocky)
            install_snapd_rhel ;;
        ubuntu|debian)
            install_snapd_ubuntu ;;
        *)
            warn "OS không xác định ($OS_ID). Thử cài snapd tự động..."
            sudo dnf install -y snapd 2>/dev/null || sudo apt-get install -y snapd 2>/dev/null || \
                error "Không cài được snapd. Cài thủ công rồi chạy lại."
    esac
else
    success "snap đã cài sẵn"
fi

# ── Cài MicroK8s ─────────────────────────────────────────────────────────────
if ! command -v microk8s &>/dev/null && [[ ! -f /var/lib/snapd/snap/bin/microk8s ]]; then
    info "Cài MicroK8s..."
    sudo snap install microk8s --classic
    
    # Thêm user hiện tại vào group microk8s
    sudo usermod -aG microk8s "$USER"
    sudo chown -R "$USER:$USER" ~/.kube 2>/dev/null || true
    success "MicroK8s installed"
else
    success "MicroK8s đã cài sẵn"
fi

# ── Tìm đúng path của microk8s ──────────────────────────────────────────────
find_microk8s() {
    for p in \
        "microk8s" \
        "/snap/bin/microk8s" \
        "/var/lib/snapd/snap/bin/microk8s" \
        "/var/snap/microk8s/current/bin/microk8s"; do
        if command -v "$p" &>/dev/null || [[ -x "$p" ]]; then
            echo "$p"; return 0
        fi
    done
    # Fallback: tìm trong snapd locations
    local found
    found=$(find /var/lib/snapd /snap -name microk8s -type f 2>/dev/null | head -1)
    [[ -n "$found" ]] && echo "$found" && return 0
    return 1
}

MICROK8S_CMD=$(find_microk8s) || error "Không tìm thấy microk8s binary. Thử: sudo snap install microk8s --classic"
info "microk8s path: $MICROK8S_CMD"

# ── Chờ MicroK8s sẵn sàng ───────────────────────────────────────────────────
info "Chờ MicroK8s khởi động (tối đa 3 phút)..."
sudo "$MICROK8S_CMD" status --wait-ready --timeout 180 || \
    warn "MicroK8s chưa ready hoàn toàn, tiếp tục thử join..."

# ── Mở firewall (nếu cần) ────────────────────────────────────────────────────
if command -v firewall-cmd &>/dev/null; then
    info "Mở ports MicroK8s trên firewall (Oracle Linux)..."
    sudo firewall-cmd --permanent --add-port=25000/tcp 2>/dev/null || true
    sudo firewall-cmd --permanent --add-port=16443/tcp 2>/dev/null || true
    sudo firewall-cmd --permanent --add-port=10250/tcp 2>/dev/null || true
    sudo firewall-cmd --permanent --add-port=10255/tcp 2>/dev/null || true
    sudo firewall-cmd --reload 2>/dev/null || true
    success "Firewall configured"
fi

# ── JOIN cluster ─────────────────────────────────────────────────────────────
echo ""
info "Joining cluster as WORKER NODE..."
info "Join URL: $JOIN_URL"
echo ""

sudo "$MICROK8S_CMD" join "$JOIN_URL" --worker

# ── Verify ───────────────────────────────────────────────────────────────────
echo ""
info "Đợi node được nhận vào cluster (30s)..."
sleep 30

echo ""
echo -e "${BOLD}══ Kết quả từ phía worker node ══${RESET}"
sudo "$MICROK8S_CMD" status 2>/dev/null | head -5 || true

echo ""
echo -e "${YELLOW}══ Kiểm tra trên MASTER (3S-COM server) ══${RESET}"
echo "  Chạy lệnh sau trên server 3S-COM để xác nhận worker đã join:"
echo ""
echo -e "  ${CYAN}sudo microk8s kubectl get nodes -o wide${RESET}"
echo ""
echo "  Kết quả mong đợi:"
echo "  NAME         STATUS   ROLES    AGE"
echo "  3s-com       Ready    <none>   ..."
echo "  k8s-master   Ready    <none>   ...  ← Node mới"
echo ""

success "Script hoàn thành! Kiểm tra trên master bằng lệnh trên."
echo ""
warn "Nếu thấy lỗi 'token expired', chạy trên 3S-COM server:"
warn "  sudo microk8s add-node"
warn "Rồi chạy lại: bash join_worker_node.sh \"<join_url_mới>\""
