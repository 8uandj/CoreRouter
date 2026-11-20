"""Backend gate for matching admitted paths to the live P4 controller."""

import re


def fetch_live_p4_topology_hash(controller_url: str) -> str:
    """Read the controller's live link/profile identity before reserving."""
    if not isinstance(controller_url, str) or not controller_url.strip():
        raise ValueError("SDN controller URL is not configured")
    import requests

    response = requests.get(controller_url.rstrip("/") + "/topology", timeout=2)
    topology = response.json()
    candidate_hash = topology.get("p4_topology_hash")
    if (response.status_code != 200
            or topology.get("ready") is not True
            or topology.get("profile_id") != "p4-path-candidate-v1"
            or not isinstance(candidate_hash, str)
            or not re.fullmatch(r"[0-9a-f]{64}", candidate_hash)):
        raise ValueError("controller topology/profile is unavailable or mismatched")
    return candidate_hash
