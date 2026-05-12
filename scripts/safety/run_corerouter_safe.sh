#!/usr/bin/env bash
# Safe wrapper for selected CoreRouter operations on a server shared with ONAP.

set -euo pipefail

CORE_ROUTER_ROOT="${CORE_ROUTER_ROOT:-/home/CoreRouter}"
SAFETY_DIR="$CORE_ROUTER_ROOT/scripts/safety"
BACKEND_SCRIPT="$CORE_ROUTER_ROOT/run_backend_docker.sh"

info() { printf '[INFO] %s\n' "$*"; }
warn() { printf '[WARN] %s\n' "$*" >&2; }
fail() { printf '[ERROR] %s\n' "$*" >&2; exit 1; }

usage() {
    cat <<USAGE
Usage: $0 {status|backend-run|backend-stop|backend-logs}

Commands:
  status        Run CoreRouter preflight and ONAP read-only health checks.
  backend-run   Run ./run_backend_docker.sh run after safety checks.
  backend-stop  Run ./run_backend_docker.sh stop.
  backend-logs  Run ./run_backend_docker.sh logs.
USAGE
}

require_core_router_root() {
    [[ -d "$CORE_ROUTER_ROOT" ]] || fail "CoreRouter root not found: $CORE_ROUTER_ROOT"
    [[ -x "$BACKEND_SCRIPT" || -f "$BACKEND_SCRIPT" ]] || fail "Backend script not found: $BACKEND_SCRIPT"
}

run_preflight() {
    (cd "$CORE_ROUTER_ROOT" && bash "$SAFETY_DIR/preflight_core_router.sh")
}

run_onap_check() {
    bash "$SAFETY_DIR/check_onap_safety.sh"
}

check_backend_port() {
    if ! command -v ss >/dev/null 2>&1; then
        warn "ss command not found; cannot inspect port 8000."
        return 0
    fi

    local listeners
    listeners="$(ss -ltnp 'sport = :8000' 2>/dev/null || true)"
    if [[ -z "$listeners" || "$listeners" != *LISTEN* ]]; then
        info "Port 8000 is free."
        return 0
    fi

    printf '%s\n' "$listeners"
    if printf '%s\n' "$listeners" | grep -Eiq '3s-com|core-router|python|uvicorn|docker'; then
        warn "Port 8000 is already in use, but it looks CoreRouter-related. run_backend_docker.sh may replace its own container."
    else
        fail "Port 8000 is occupied by a non-CoreRouter-looking process. Stop/inspect it manually before backend-run."
    fi
}

main() {
    local command="${1:-}"

    require_core_router_root

    case "$command" in
        status)
            run_preflight
            run_onap_check
            ;;
        backend-run)
            run_preflight
            check_backend_port
            (cd "$CORE_ROUTER_ROOT" && bash "$BACKEND_SCRIPT" run)
            ;;
        backend-stop)
            run_preflight
            (cd "$CORE_ROUTER_ROOT" && bash "$BACKEND_SCRIPT" stop)
            ;;
        backend-logs)
            (cd "$CORE_ROUTER_ROOT" && bash "$BACKEND_SCRIPT" logs)
            ;;
        -h|--help|help|"")
            usage
            ;;
        *)
            usage
            fail "Unsupported command: $command"
            ;;
    esac
}

main "$@"
