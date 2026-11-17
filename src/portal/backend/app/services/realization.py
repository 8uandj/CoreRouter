"""Immutable admission identity and strict forwarding-payload checks."""

from dataclasses import dataclass
import ipaddress
import re
from typing import Any, Mapping, Optional, Tuple


@dataclass(frozen=True)
class AdmittedRealization:
    request_id: str
    operation_id: str
    topology_hash: str
    profile_id: str
    sid_stack: Tuple[str, ...]
    forwarding_sid: Optional[str]

    def __post_init__(self):
        for key in ("request_id", "operation_id", "profile_id"):
            value = getattr(self, key)
            if not isinstance(value, str) or not value.strip():
                raise ValueError("admitted realization requires nonempty " + key)
        if not isinstance(self.topology_hash, str) or not re.fullmatch(r"[0-9a-f]{64}", self.topology_hash):
            raise ValueError("admitted realization requires a SHA-256 topology_hash")
        if not isinstance(self.sid_stack, tuple) or not self.sid_stack:
            raise ValueError("admitted realization requires an immutable nonempty sid_stack")
        try:
            for sid in self.sid_stack:
                if ipaddress.ip_address(sid).version != 6:
                    raise ValueError
        except (ValueError, TypeError):
            raise ValueError("admitted realization sid_stack must contain IPv6 addresses") from None
        if self.forwarding_sid is None:
            return
        try:
            if ipaddress.ip_address(self.forwarding_sid).version != 6:
                raise ValueError
        except (ValueError, TypeError):
            raise ValueError("admitted realization forwarding_sid must be IPv6") from None
        if self.forwarding_sid not in self.sid_stack:
            raise ValueError("forwarding_sid is absent from admitted sid_stack")


def validate_realization_payload(admitted: AdmittedRealization, payload: Mapping[str, Any]) -> None:
    """Reject any actuation payload that differs from its admitted handle."""
    if not isinstance(admitted, AdmittedRealization) or not isinstance(payload, Mapping):
        raise ValueError("admitted realization handle and mapping payload are required")
    if admitted.forwarding_sid is None:
        raise ValueError("no supported forwarding realization is available")
    for key in ("request_id", "operation_id", "topology_hash", "profile_id"):
        if payload.get(key) != getattr(admitted, key):
            raise ValueError("controller payload does not match admitted realization: " + key)
    rules = payload.get("new_rules")
    if not isinstance(rules, list) or any(not isinstance(rule, Mapping) for rule in rules):
        raise ValueError("controller payload does not match admitted realization: new_rules")
    payload_sids = tuple(rule.get("sid") for rule in rules if rule.get("type") == "srv6_sid")
    if payload_sids != admitted.sid_stack:
        raise ValueError("controller payload does not match admitted realization: sid_stack")
