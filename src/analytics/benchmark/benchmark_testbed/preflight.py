from __future__ import annotations

from typing import Dict, Tuple

from .http_client import TestbedClient


def run_preflight(client: TestbedClient) -> Tuple[bool, Dict[str, object]]:
    checks: Dict[str, object] = {}

    api_code, api_body, _ = client.health()
    checks["api_health"] = {"ok": api_code == 200, "status_code": api_code, "body": api_body}

    steer_code, steer_body, _ = client.steer_status()
    checks["sdn_steer"] = {"ok": steer_code == 200, "status_code": steer_code, "body": steer_body}

    drops_code, drops_body, _ = client.msd_drops()
    checks["sdn_msd_drops"] = {
        "ok": drops_code == 200,
        "status_code": drops_code,
        "body": drops_body,
    }

    ok = all(bool(v.get("ok")) for v in checks.values() if isinstance(v, dict))
    return ok, checks

