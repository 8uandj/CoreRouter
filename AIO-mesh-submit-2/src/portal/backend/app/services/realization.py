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
    switch_path: Tuple[int, ...] = ()
    p4_topology_hash: Optional[str] = None

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
        if self.profile_id == "p4-path-candidate-v1":
            if (not isinstance(self.switch_path, tuple)
                    or len(self.switch_path) != len(self.sid_stack)
                    or len(self.switch_path) < 2
                    or any(not isinstance(node, int) or isinstance(node, bool)
                           or not 1 <= node <= 10 for node in self.switch_path)):
                raise ValueError("P4 realization requires a complete immutable switch_path")
            expected_sids = tuple("fc00:{}::1".format(node)
                                  for node in reversed(self.switch_path))
            if self.sid_stack != expected_sids or self.forwarding_sid != expected_sids[0]:
                raise ValueError("P4 realization forwarding path is inconsistent")
            if not isinstance(self.p4_topology_hash, str) or not re.fullmatch(
                    r"[0-9a-f]{64}", self.p4_topology_hash):
                raise ValueError("P4 realization requires the live P4 topology hash")


def validate_realization_payload(admitted: AdmittedRealization, payload: Mapping[str, Any]) -> None:
    """Reject any actuation payload that differs from its admitted handle."""
    if not isinstance(admitted, AdmittedRealization) or not isinstance(payload, Mapping):
        raise ValueError("admitted realization handle and mapping payload are required")
    if admitted.forwarding_sid is None:
        raise ValueError("no supported forwarding realization is available")
    for key in ("request_id", "operation_id", "topology_hash", "profile_id"):
        if payload.get(key) != getattr(admitted, key):
            raise ValueError("controller payload does not match admitted realization: " + key)
    if payload.get("p4_topology_hash") != admitted.p4_topology_hash:
        raise ValueError("controller payload does not match admitted realization: p4_topology_hash")
    payload_path = payload.get("switch_path")
    payload_sids = payload.get("sid_stack")
    if not isinstance(payload_path, (list, tuple)):
        raise ValueError("controller payload does not match admitted realization: switch_path")
    if not isinstance(payload_sids, (list, tuple)):
        raise ValueError("controller payload does not match admitted realization: sid_stack")
    if tuple(payload_path) != admitted.switch_path:
        raise ValueError("controller payload does not match admitted realization: switch_path")
    if tuple(payload_sids) != admitted.sid_stack:
        raise ValueError("controller payload does not match admitted realization: sid_stack")
