"""
state_manager.py — Local State Manager for 3S-COM Orchestration (Phase 7 Alignment)
DONG BO 100% VOI TRAINING ENVIRONMENT (src/orchestration/jo_vdpr/env.py)
TUAN THU QUY TAC KIEN TRUC 16 (HYSTERESIS GATE)
"""

import threading
import numpy as np
import time
import math
import os
import hashlib
import json
from src.core.reservation_store import ReservationStore
from dataclasses import dataclass
from typing import Dict, List, Any, Optional, Tuple

from src.orchestration.jo_vdpr.topology import DEFAULT_TOPO, TopologyManager

# =============================================================================
# CONSTANTS (TUAN THU .ai/ARCHITECTURE.MD)
# =============================================================================
ALERT_CPU_THRESHOLD = 0.80
AI_ENGAGE_THRESHOLD = 0.45
AI_RELEASE_THRESHOLD = 0.35
HYSTERESIS_EPSILON = 1e-6  # avoid float32 state rounding across exact thresholds
MAX_CPU = 100.0
MAX_RAM = 100.0

@dataclass
class NetworkSnapshot:
    mode: str
    avg_cpu: float
    avg_msd_usage: float
    global_utilization: float
    alert_flag: bool
    nodes: List[Dict[str, Any]]
    state: np.ndarray 
    latency_matrix: np.ndarray
    adj_matrix: np.ndarray
    msd_limits: np.ndarray
    node_names: List[str]
    forecast_alerts: List[bool]
    state_version: int
    telemetry_age_s: List[Optional[float]]
    stale_telemetry_nodes: List[int]

class NetworkStateManager:
    """
    Quan ly trang thai tai nguyen mang Local (Singleton).
    Dam bao tinh Thread-safe va tuan thu Hysteresis Gate.
    """
    
    def __init__(
        self, topology=DEFAULT_TOPO, topology_name: Optional[str] = None,
        max_telemetry_age_s: Optional[float] = None, reservation_path=None,
    ):
        self.topology = TopologyManager(topology_name) if topology_name else topology
        self.num_nodes = self.topology.num_nodes
        self._lock = threading.Lock()
        self._state_version = 0
        if max_telemetry_age_s is not None and (not math.isfinite(max_telemetry_age_s) or max_telemetry_age_s <= 0):
            raise ValueError("max_telemetry_age_s must be positive or None")
        self.max_telemetry_age_s = max_telemetry_age_s
        self._resource_telemetry_at: List[Optional[float]] = [None] * self.num_nodes
        self._resource_field_at = [[None, None, None] for _ in range(self.num_nodes)]
        self._mode = "heuristic" # Mac dinh bat dau bang Heuristic
        
        # State matrix: [CPU_used, RAM_used, MSD_used]
        self._state = np.zeros((self.num_nodes, 3), dtype=np.float32)
        self._reported_resources = np.zeros((self.num_nodes, 2), dtype=np.float32)
        self._reported_msd = np.zeros(self.num_nodes, dtype=np.float32)
        self._alert_active = False
        self._forecast_alerts = np.zeros(self.num_nodes, dtype=bool)
        
        # Registry theo doi thuc the (Ho tro Phase 7 Proactive Migration)
        self._active_vnfs: Dict[str, Dict[str, Any]] = {}
        self._pending_reservations: Dict[str, Dict[str, Any]] = {}
        self._anonymous_reservations: List[Dict[str, Any]] = []
        self._reservation_store = None
        self._persistence_failed = False
        if reservation_path is not None:
            self.enable_persistence(reservation_path)

    def _topology_identity(self):
        profile = {"names": list(self.topology.names), "msd": self.topology.msd_limits.tolist(),
                   "adjacency": self.topology.adj_matrix.tolist(),
                   "latency": self.topology.latency_matrix.tolist()}
        return hashlib.sha256(json.dumps(profile, sort_keys=True).encode()).hexdigest()

    def _durable_payload(self):
        return {"schema": 1, "topology": self._topology_identity(),
                "state_version": self._state_version,
                "reported_resources": self._reported_resources.tolist(),
                "reported_msd": self._reported_msd.tolist(),
                "active": self._active_vnfs, "pending": self._pending_reservations,
                "anonymous": self._anonymous_reservations}

    def _restore_payload(self, payload):
        if payload.get("schema") != 1 or payload.get("topology") != self._topology_identity():
            raise ValueError("reservation snapshot schema/topology mismatch")
        resources = np.asarray(payload["reported_resources"], dtype=np.float32)
        msd = np.asarray(payload["reported_msd"], dtype=np.float32)
        if (resources.shape != (self.num_nodes, 2) or msd.shape != (self.num_nodes,)
                or not np.all(np.isfinite(resources)) or not np.all(np.isfinite(msd))
                or np.any(resources < 0) or np.any(msd < 0)):
            raise ValueError("invalid reservation observation snapshot")
        active, pending, anonymous = payload["active"], payload["pending"], payload["anonymous"]
        if not isinstance(active, dict) or not isinstance(pending, dict) or not isinstance(anonymous, list):
            raise ValueError("invalid reservation registry snapshot")
        for name, item in active.items():
            if not isinstance(name, str) or not name.strip():
                raise ValueError("invalid reservation identity")
        for item in list(active.values()) + anonymous:
            depth = item["msd_req"]
            if item.get("accounting_unknown") and depth == 0:
                depth = 1  # zero is permitted only for an explicitly unknown profile
            if not self._valid_reservation(item["v_place"], item["v_route"],
                                           item["cpu_req"], item["ram_req"], depth):
                raise ValueError("invalid reservation profile snapshot")
        for name, item in pending.items():
            if name not in active or any(item[key] != active[name][key] for key in
                    ("v_place", "v_route", "cpu_req", "ram_req", "msd_req")):
                raise ValueError("pending reservation does not match active profile")
        version = payload["state_version"]
        if not isinstance(version, int) or isinstance(version, bool) or version < 0:
            raise ValueError("invalid reservation state version")
        self._reported_resources[:] = resources
        self._reported_msd[:] = msd
        self._active_vnfs, self._pending_reservations = active, pending
        self._anonymous_reservations = anonymous
        self._state_version = version
        self._rebuild_resource_state()
        # Local monotonic ingestion timestamps never establish freshness after restart.
        self._resource_telemetry_at = [None] * self.num_nodes
        self._resource_field_at = [[None, None, None] for _ in range(self.num_nodes)]

    def enable_persistence(self, path):
        with self._lock:
            if self._reservation_store is not None:
                from pathlib import Path
                if self._reservation_store.path != str(Path(path).resolve()):
                    raise RuntimeError("reservation persistence already configured")
                return
            store = ReservationStore(path)
            try:
                saved = store.load()
                if saved is not None:
                    if self._active_vnfs or self._anonymous_reservations:
                        raise RuntimeError("cannot merge durable ledger with live reservations")
                    self._restore_payload(saved)
                self._reservation_store = store
                self._checkpoint()
            except Exception:
                self._reservation_store = None
                self._persistence_failed = True
                store.close()
                raise

    def _checkpoint(self):
        """Caller holds admission lock; persist before acknowledging a mutation."""
        self._state_version += 1
        if self._reservation_store is not None:
            try:
                self._reservation_store.save(self._durable_payload())
            except Exception as exc:
                self._persistence_failed = True
                raise RuntimeError("reservation persistence failed; admission latched closed") from exc

    def close(self):
        with self._lock:
            self._persistence_failed = True
            if self._reservation_store is not None:
                self._reservation_store.close()

    def reset(self) -> None:
        with self._lock:
            if any(item.get("actuation_requested") or item.get("accounting_unknown")
                   or item.get("is_pending") is False for item in self._active_vnfs.values()):
                raise ValueError("lifecycle_cleanup_required")
            self._state.fill(0)
            self._reported_msd.fill(0)
            self._reported_resources.fill(0)
            self._resource_telemetry_at = [None] * self.num_nodes
            self._resource_field_at = [[None, None, None] for _ in range(self.num_nodes)]
            self._alert_active = False
            self._forecast_alerts.fill(False)
            self._active_vnfs.clear()
            self._pending_reservations.clear()
            self._anonymous_reservations.clear()
            self._mode = "heuristic"
            self._checkpoint()

    def snapshot(self) -> NetworkSnapshot:
        with self._lock:
            state = self._state.copy()
            cpu_utils = state[:, 0] / MAX_CPU
            msd_utils = state[:, 2] / self.topology.msd_limits
            
            avg_cpu = float(np.mean(cpu_utils))
            avg_msd_usage = float(np.mean(msd_utils))
            global_util = max(avg_cpu, avg_msd_usage)
            now = time.monotonic()
            telemetry_ages = [
                None if timestamp is None else max(0.0, now - timestamp)
                for timestamp in self._resource_telemetry_at
            ]
            stale_nodes = (
                [node for node, age in enumerate(telemetry_ages)
                 if age is None or age > self.max_telemetry_age_s]
                if self.max_telemetry_age_s is not None else []
            )
            
            node_list = []
            for i in range(self.num_nodes):
                node_list.append({
                    "id": i,
                    "name": self.topology.names[i],
                    "cpu_util": float(cpu_utils[i] * 100.0),
                    "ram_util": float((state[i, 1] / MAX_RAM) * 100.0),
                    "msd_util": float(msd_utils[i] * 100.0),
                    "alert": bool(cpu_utils[i] > ALERT_CPU_THRESHOLD or self._forecast_alerts[i])
                })
            
            return NetworkSnapshot(
                mode=self._mode,
                avg_cpu=avg_cpu,
                avg_msd_usage=avg_msd_usage,
                global_utilization=global_util,
                alert_flag=self._alert_active,
                nodes=node_list,
                state=state,
                latency_matrix=self.topology.latency_matrix,
                adj_matrix=self.topology.adj_matrix,
                msd_limits=self.topology.msd_limits,
                node_names=self.topology.names,
                forecast_alerts=[bool(x) for x in self._forecast_alerts],
                state_version=self._state_version,
                telemetry_age_s=telemetry_ages,
                stale_telemetry_nodes=stale_nodes,
            )

    def can_reserve(self, node: int, cpu_req: float, ram_req: float, msd_req: int) -> bool:
        """Check placement CPU/RAM capacity and per-list SID depth capability.

        MSD is a per-SFC list limit, not an additive node resource. The state
        column stores the greatest active list depth routed through each node
        for observation only; the route-specific capability check is performed
        by try_reserve.
        """
        cpu_used = self._state[node, 0]
        ram_used = self._state[node, 1]
        return (
            cpu_used + cpu_req <= MAX_CPU
            and ram_used + ram_req <= MAX_RAM
        )

    def _valid_reservation(self, v_place: int, v_route: int, cpu_req: float,
                           ram_req: float, msd_req: int) -> bool:
        try:
            nodes_valid = all(
                isinstance(node, (int, np.integer)) and not isinstance(node, bool)
                and 0 <= int(node) < self.num_nodes
                for node in (v_place, v_route)
            )
            numeric = all(
                isinstance(value, (int, float, np.number)) and not isinstance(value, (bool, np.bool_))
                for value in (cpu_req, ram_req)
            )
            depth_type_valid = isinstance(msd_req, (int, np.integer, float, np.floating))
            cpu, ram = float(cpu_req), float(ram_req)
            depth = int(msd_req)
            return bool(
                nodes_valid and numeric and depth_type_valid
                and math.isfinite(cpu) and math.isfinite(ram)
                and cpu >= 0 and ram >= 0
                and not isinstance(msd_req, bool) and depth == msd_req and depth > 0
            )
        except (TypeError, ValueError, OverflowError):
            return False

    def try_reserve(
        self,
        v_place: int,
        v_route: int,
        cpu_req: float,
        ram_req: float,
        msd_req: int,
        vnf_name: Optional[str] = None,
        expected_state_version: Optional[int] = None,
    ) -> Tuple[bool, Optional[str]]:
        with self._lock:
            if self._persistence_failed:
                return False, "reservation_persistence_unavailable"
            if expected_state_version is not None and expected_state_version != self._state_version:
                return False, "stale_state_version"
            if self.max_telemetry_age_s is not None:
                now = time.monotonic()
                if any(
                    timestamp is None or now - timestamp > self.max_telemetry_age_s
                    for timestamp in self._resource_telemetry_at
                ):
                    return False, "stale_telemetry"
            if any(item.get("accounting_unknown") for item in self._active_vnfs.values()):
                return False, "untracked_deployment_resources"
            if not self._valid_reservation(v_place, v_route, cpu_req, ram_req, msd_req):
                return False, "invalid_reservation"
            if vnf_name is not None and (not isinstance(vnf_name, str) or not vnf_name.strip()):
                return False, "invalid_reservation_name"
            if vnf_name is not None and vnf_name in self._active_vnfs:
                return False, "duplicate_reservation"
            if not self.can_reserve(v_place, cpu_req, ram_req, msd_req):
                return False, "placement_node_full"

            if msd_req > float(self.topology.msd_limits[v_route]):
                return False, "routing_node_msd_exceeded"

            self._state[v_place, 0] += cpu_req
            self._state[v_place, 1] += ram_req
            self._state[v_route, 2] = max(self._state[v_route, 2], msd_req)
            record = {
                    "v_place": v_place, "v_route": v_route,
                    "cpu_req": cpu_req, "ram_req": ram_req, "msd_req": msd_req
                }
            if vnf_name is not None:
                self._active_vnfs[vnf_name] = record
                self._pending_reservations[vnf_name] = {
                    **record,
                    "timestamp": time.time()
                }
            else:
                self._anonymous_reservations.append(record)
            self._checkpoint()
            return True, None

    def reserve_resources(
        self,
        v_place: int,
        v_route: int,
        cpu_req: float,
        ram_req: float,
        msd_req: int,
        vnf_name: Optional[str] = None,
        expected_state_version: Optional[int] = None,
    ) -> Tuple[bool, Optional[str]]:
        """Backwards compatibility alias for try_reserve."""
        return self.try_reserve(
            v_place, v_route, cpu_req, ram_req, msd_req, vnf_name,
            expected_state_version=expected_state_version,
        )

    def mark_actuation_requested(self, vnf_name: str) -> None:
        with self._lock:
            if vnf_name not in self._active_vnfs:
                raise ValueError("unknown reservation")
            self._active_vnfs[vnf_name]["actuation_requested"] = True
            self._checkpoint()

    def release_unactuated_reservation(self, vnf_name: str) -> Tuple[bool, Optional[str]]:
        """TTL may release a selection-only record, never an actuation in flight."""
        with self._lock:
            record = self._active_vnfs.get(vnf_name)
            if record is None:
                return True, None  # idempotent response for the same request identity
            if record.get("is_pending") is False:
                return False, "deployed_teardown_required"
            if record.get("actuation_requested"):
                return False, "actuation_in_flight"
            if record.get("accounting_unknown"):
                return False, "unknown_deployment_profile"
            if (record.get("presence_unconfirmed") or not record.get("is_pending", True)):
                return False, "lifecycle_cleanup_required"
            self._pending_reservations.pop(vnf_name, None)
            self._active_vnfs.pop(vnf_name)
            self._subtract_placement(record)
            self._recompute_msd()
            self._checkpoint()
            return True, None

    def release_confirmed_absent(self, vnf_name: str) -> Tuple[bool, Optional[str]]:
        """Release a deployed record only after the caller observed its absence.

        Kubernetes sync keeps vanished deployed records as presence_unconfirmed;
        this is the explicit lifecycle cleanup for that state. Pending
        (in-flight) reservations and records still listed by Kubernetes are kept.
        """
        with self._lock:
            record = self._active_vnfs.get(vnf_name)
            if record is None:
                return True, None
            if vnf_name in self._pending_reservations or record.get("is_pending", False):
                return False, "actuation_in_flight"
            if not record.get("presence_unconfirmed"):
                return False, "still_listed_by_kubernetes"
            self._active_vnfs.pop(vnf_name)
            self._subtract_placement(record)
            self._recompute_msd()
            self._checkpoint()
            return True, None

    def release_resources(self, vnf_name: str) -> None:
        with self._lock:
            if vnf_name in self._pending_reservations:
                self._pending_reservations.pop(vnf_name)
            if vnf_name not in self._active_vnfs:
                return
            data = self._active_vnfs.pop(vnf_name)
            self._subtract_placement(data)
            self._recompute_msd()
            self._checkpoint()

    def _subtract_placement(self, data: Dict[str, Any]) -> None:
        node = int(data["v_place"])
        self._state[node, 0] = max(0.0, self._state[node, 0] - data["cpu_req"])
        self._state[node, 1] = max(0.0, self._state[node, 1] - data["ram_req"])

    def _recompute_msd(self) -> None:
        self._state[:, 2] = self._reported_msd
        for item in list(self._active_vnfs.values()) + self._anonymous_reservations:
            node = int(item["v_route"])
            self._state[node, 2] = max(self._state[node, 2], item["msd_req"])

    def free_resources(
        self,
        v_place: int,
        v_route: int,
        cpu_req: float,
        ram_req: float,
        msd_req: int,
    ) -> None:
        """Release resources for TTL-based SFC expiry without a tracked VNF name."""
        with self._lock:
            target = (v_place, v_route, cpu_req, ram_req, msd_req)
            for index in range(len(self._anonymous_reservations) - 1, -1, -1):
                item = self._anonymous_reservations[index]
                key = (item["v_place"], item["v_route"], item["cpu_req"], item["ram_req"], item["msd_req"])
                if key == target:
                    self._anonymous_reservations.pop(index)
                    self._subtract_placement(item)
                    self._recompute_msd()
                    self._checkpoint()
                    break

    def resolve_node_id(self, vnf_name: str, location: str) -> int:
        """Map a VNF name and its location label to virtual node index 0-9."""
        name_lower = vnf_name.lower()
        loc_lower = location.lower()
        
        # Check direct location mappings
        if "hn" in loc_lower or "hanoi" in loc_lower:
            if "-hp" in name_lower: return 1
            if "-nb" in name_lower: return 2
            return 0
        if "hp" in loc_lower or "haiphong" in loc_lower:
            return 1
        if "nb" in loc_lower or "ninhbinh" in loc_lower:
            return 2
        if "vinh" in loc_lower:
            return 3
        if "hue" in loc_lower:
            return 4
        if "dn" in loc_lower or "danang" in loc_lower:
            if "-vinh" in name_lower: return 3
            if "-hue" in name_lower: return 4
            return 5
        if "qn" in loc_lower or "quynhon" in loc_lower:
            return 6
        if "nt" in loc_lower or "nhatrang" in loc_lower:
            return 7
        if "hcm" in loc_lower or "hochiminh" in loc_lower:
            if "-qn" in name_lower: return 6
            if "-nt" in name_lower: return 7
            if "-ct" in name_lower: return 9
            return 8
        if "ct" in loc_lower or "cantho" in loc_lower:
            return 9
            
        # Check fallback pattern based on names and parent cluster keys
        if "hanoi-1" in loc_lower or "k8s-master" in loc_lower:
            if "-hp" in name_lower: return 1
            if "-nb" in name_lower: return 2
            return 0
        if "danang-1" in loc_lower or "worker1" in loc_lower:
            if "-vinh" in name_lower: return 3
            if "-hue" in name_lower: return 4
            return 5
        if "hcm-1" in loc_lower or "worker2" in loc_lower:
            if "-qn" in name_lower: return 6
            if "-nt" in name_lower: return 7
            if "-ct" in name_lower: return 9
            return 8
            
        # Name-based checks
        if "-hp" in name_lower: return 1
        if "-nb" in name_lower: return 2
        if "-vinh" in name_lower: return 3
        if "-hue" in name_lower: return 4
        if "-qn" in name_lower: return 6
        if "-nt" in name_lower: return 7
        if "-ct" in name_lower: return 9
        
        # Ultimate fallback
        return 0

    def sync_with_kubernetes(self, k8s_vnfs: List[Dict[str, Any]]) -> None:
        """Synchronize in-memory VNF list and resource states with live Kubernetes deployments.
        Pending reservations remain charged until explicitly released or observed
        as deployments. Absence from a list is not proof of safe rollback.
        """
        with self._lock:
            # 2. Check which pending reservations have appeared in k8s_vnfs
            k8s_names = {vnf["id"] for vnf in k8s_vnfs}
            for name in list(self._pending_reservations.keys()):
                if name in k8s_names:
                    self._pending_reservations.pop(name)
            
            # 3. Rebuild active VNFs registry
            new_active_vnfs = {}
            
            # First, add the actual VNFs from Kubernetes
            for vnf in k8s_vnfs:
                name = vnf["id"]
                location = vnf["data"].get("location", "auto")
                
                # Resolve node index for the VNF
                node_idx = self.resolve_node_id(name, location)
                
                # If we had it in our old active_vnfs or pending reservations, preserve its resource requirements
                if name in self._active_vnfs:
                    ref = self._active_vnfs[name]
                    cpu_req = ref.get("cpu_req", 10.0)
                    ram_req = ref.get("ram_req", 5.0)
                    msd_req = ref.get("msd_req", 2)
                    v_place = ref.get("v_place", node_idx)
                    v_route = ref.get("v_route", node_idx)
                else:
                    # Deployment lists do not supply admission units or SID
                    # realization. Never invent a 10%/5%/2-SID profile.
                    cpu_req = 0.0
                    ram_req = 0.0
                    msd_req = 0
                    v_place = node_idx
                    v_route = node_idx
                
                new_active_vnfs[name] = {
                    **self._active_vnfs.get(name, {}),
                    "v_place": v_place,
                    "v_route": v_route,
                    "cpu_req": cpu_req,
                    "ram_req": ram_req,
                    "msd_req": msd_req,
                    "is_pending": False,
                    "presence_unconfirmed": False,
                    "deployment_ready": (vnf.get("desired", 0) > 0
                                         and vnf.get("ready", 0) >= vnf.get("desired", 0)),
                    "accounting_unknown": (name not in self._active_vnfs
                        or self._active_vnfs[name].get("accounting_unknown", False)),
                }
            
            # Next, add any pending reservations that haven't appeared in K8s yet
            for name, ref in self._pending_reservations.items():
                new_active_vnfs[name] = {
                    **self._active_vnfs.get(name, {}),
                    "v_place": ref["v_place"],
                    "v_route": ref["v_route"],
                    "cpu_req": ref["cpu_req"],
                    "ram_req": ref["ram_req"],
                    "msd_req": ref["msd_req"],
                    "is_pending": True
                }
                
            # A missing list entry may be transient, or Pods/rules may still
            # exist. Only explicit confirmed lifecycle cleanup releases it.
            for name, ref in self._active_vnfs.items():
                if name not in new_active_vnfs:
                    new_active_vnfs[name] = {**ref, "presence_unconfirmed": True, "deployment_ready": False}
            self._active_vnfs = new_active_vnfs
            
            self._rebuild_resource_state()
            self._checkpoint()

    def _rebuild_resource_state(self) -> None:
        """Caller holds lock. Retain observations plus conservative local charges.

        Telemetry does not identify which reservations it already includes.
        Therefore do not subtract guessed overlap from observed utilization.
        """
        self._state[:, :2] = self._reported_resources
        for item in list(self._active_vnfs.values()) + self._anonymous_reservations:
            self._state[item["v_place"], 0] += item["cpu_req"]
            self._state[item["v_place"], 1] += item["ram_req"]
        self._recompute_msd()

    def as_public_dict(self) -> Dict[str, Any]:
        """Return the UI/API-safe snapshot shape used by orchestration routes."""
        snap = self.snapshot()
        return {
            "mode": snap.mode,
            "state_version": snap.state_version,
            "reservation_persistence": ("failed" if self._persistence_failed else
                                       "durable" if self._reservation_store is not None else "memory"),
            "telemetry_age_s": snap.telemetry_age_s,
            "stale_telemetry_nodes": snap.stale_telemetry_nodes,
            "avg_cpu": snap.avg_cpu,
            "avg_msd_usage": snap.avg_msd_usage,
            "global_utilization": snap.global_utilization,
            "alert_flag": snap.alert_flag,
            "nodes": snap.nodes,
            "unaccounted_vnfs": sorted(name for name, data in self._active_vnfs.items()
                                       if data.get("accounting_unknown")),
            "active_vnfs": [
                {"name": name, **data}
                for name, data in self._active_vnfs.items()
            ],
            "forecast_alerts": snap.forecast_alerts,
        }

    def get_vnfs_on_node(self, node_id: int) -> List[Dict[str, Any]]:
        with self._lock:
            return [{"name": name, **data} for name, data in self._active_vnfs.items() 
                    if data["v_place"] == node_id or data["v_route"] == node_id]

    def set_forecast_alert(self, alert: bool) -> None:
        with self._lock:
            changed = self._alert_active != bool(alert) or (not alert and bool(np.any(self._forecast_alerts)))
            self._alert_active = bool(alert)
            if not alert:
                self._forecast_alerts.fill(False)
            if changed:
                self._checkpoint()

    def set_node_forecast_alert(self, node_id: int, alert: bool) -> None:
        with self._lock:
            node = int(node_id)
            old_node_alert = bool(self._forecast_alerts[node])
            old_global_alert = self._alert_active
            self._forecast_alerts[node] = bool(alert)
            self._alert_active = bool(np.any(self._forecast_alerts))
            if old_node_alert != bool(alert) or old_global_alert != self._alert_active:
                self._checkpoint()

    def update_node_telemetry(
        self,
        node_id: int,
        cpu_util: Optional[float] = None,
        ram_util: Optional[float] = None,
        msd_used: Optional[float] = None,
        msd_util: Optional[float] = None,
        alert: Optional[bool] = None,
    ) -> None:
        """Ingest live telemetry as absolute node resource state.

        cpu_util/ram_util can be supplied as either 0..1 ratios or 0..100 percents.
        msd_used is absolute SID depth; msd_util is 0..1 or 0..100 utilization.
        """
        if (not isinstance(node_id, (int, np.integer)) or isinstance(node_id, (bool, np.bool_))
                or not 0 <= int(node_id) < self.num_nodes):
            raise ValueError("invalid telemetry node")
        for value in (cpu_util, ram_util, msd_used, msd_util):
            if value is not None and (isinstance(value, (bool, np.bool_))
                    or not isinstance(value, (int, float, np.number))
                    or not math.isfinite(float(value)) or value < 0):
                raise ValueError("telemetry resource values must be finite and nonnegative")
        node = int(node_id)
        with self._lock:
            if cpu_util is not None:
                cpu = float(cpu_util)
                self._reported_resources[node, 0] = np.clip(cpu * 100.0 if cpu <= 1.0 else cpu, 0.0, MAX_CPU)
            if ram_util is not None:
                ram = float(ram_util)
                self._reported_resources[node, 1] = np.clip(ram * 100.0 if ram <= 1.0 else ram, 0.0, MAX_RAM)
            if msd_used is not None:
                self._reported_msd[node] = np.clip(float(msd_used), 0.0, float(self.topology.msd_limits[node]))
            elif msd_util is not None:
                util = float(msd_util)
                ratio = util if util <= 1.0 else util / 100.0
                self._reported_msd[node] = np.clip(
                    ratio * float(self.topology.msd_limits[node]),
                    0.0,
                    float(self.topology.msd_limits[node]),
                )
            if msd_used is not None or msd_util is not None:
                self._state[node, 2] = self._reported_msd[node]
                for item in list(self._active_vnfs.values()) + self._anonymous_reservations:
                    if item["v_route"] == node:
                        self._state[node, 2] = max(self._state[node, 2], item["msd_req"])
            if cpu_util is not None or ram_util is not None:
                self._state[node, :2] = self._reported_resources[node]
                for item in list(self._active_vnfs.values()) + self._anonymous_reservations:
                    if item["v_place"] == node:
                        self._state[node, 0] += item["cpu_req"]
                        self._state[node, 1] += item["ram_req"]
            if cpu_util is not None or ram_util is not None or msd_used is not None or msd_util is not None:
                now = time.monotonic()
                for column, supplied in enumerate((cpu_util is not None, ram_util is not None,
                                                   msd_used is not None or msd_util is not None)):
                    if supplied:
                        self._resource_field_at[node][column] = now
                timestamps = self._resource_field_at[node]
                self._resource_telemetry_at[node] = (
                    min(timestamps) if all(t is not None for t in timestamps) else None
                )
            if alert is not None:
                self._forecast_alerts[node] = bool(alert)
            self._alert_active = bool(np.any(self._forecast_alerts))
            self._checkpoint()

    def choose_mode(self) -> Any:
        """
        Decision Gate (Hysteresis): Quyết định chuyển đổi Heuristic <-> DRL.
        Tuan thu Quy tac 16: AI_ENGAGE=0.45, AI_RELEASE=0.35
        """
        from dataclasses import make_dataclass
        Gate = make_dataclass("Gate", [("mode", str), ("reason", str), ("global_utilization", float)])
        
        snap = self.snapshot()
        u = snap.global_utilization

        with self._lock:
            # Logic Cong Tre (Hysteresis)
            reason = "hold"
            old_mode = self._mode
            if self._mode == "heuristic":
                if u > AI_ENGAGE_THRESHOLD + HYSTERESIS_EPSILON or self._alert_active:
                    self._mode = "drl"
                    reason = "engage_drl_alert_or_utilization"
            else: # dang o che do drl
                if u < AI_RELEASE_THRESHOLD - HYSTERESIS_EPSILON and not self._alert_active:
                    self._mode = "heuristic"
                    reason = "release_to_heuristic_low_utilization"
            if self._mode != old_mode:
                self._checkpoint()
            
            return Gate(mode=self._mode, reason=reason, global_utilization=u)

    def action_mask(self, request: Any) -> np.ndarray:
        """Return a flat N² mask indexed by ``placement * N + route``.

        The mask matches the training environment's ``Discrete(N*N)`` action
        space and can represent placement CPU/RAM and route MSD feasibility for
        each pair. Reservation still rechecks the selected pair atomically.
        """
        with self._lock:
            masks = np.zeros(self.num_nodes * self.num_nodes, dtype=bool)
            for place in range(self.num_nodes):
                required_place = getattr(request, "required_v_place", None)
                if required_place is not None and place != int(required_place):
                    continue
                if not self.can_reserve(place, request.cpu_req, request.ram_req, request.msd_req):
                    continue
                for route in range(self.num_nodes):
                    if int(request.msd_req) <= float(self.topology.msd_limits[route]):
                        masks[place * self.num_nodes + route] = True
            return masks

    def to_observation(self, request: Any) -> np.ndarray:
        """
        Chuyen doi sang vector Observation chuan GNN (N*6 + 13).
        DONG BO 100% VOI src/orchestration/jo_vdpr/env.py
        """
        snap = self.snapshot()
        topology = self.topology
        node_feat_dim, req_dim, svc_dim, gc_dim = 6, 3, 5, 5
        
        obs = np.zeros((self.num_nodes * node_feat_dim + req_dim + svc_dim + gc_dim), dtype=np.float32)
        geo_norm = topology.lats / (np.max(topology.lats) + 1e-9)

        for node in range(self.num_nodes):
            cpu_u = snap.state[node, 0] / 100.0 
            ram_u = snap.state[node, 1] / 100.0
            msd_u = snap.state[node, 2] / float(topology.msd_limits[node])
            msd_f = max(0.0, 1.0 - msd_u)
            alert = 1.0 if cpu_u > ALERT_CPU_THRESHOLD else 0.0
            base = node * node_feat_dim
            obs[base:base+6] = [cpu_u, ram_u, msd_u, msd_f, alert, float(geo_norm[node])]
            
        br = self.num_nodes * node_feat_dim
        obs[br:br+3] = [request.cpu_req/100.0, request.ram_req/100.0, request.msd_req/float(topology.msd_limits.max())]
        
        svc_map = {"Video": 0, "VoIP": 1, "Data": 2, "IoT": 3, "Attack": 4}
        obs[br+3+svc_map.get(request.service_type, 2)] = 1.0
        
        gc_base = br + req_dim + svc_dim
        obs[gc_base:gc_base+5] = [
            snap.avg_cpu, 
            snap.avg_msd_usage, 
            obs[br], # req_intensity
            (request.msd_req * 0.05) / 0.3, # srv6_norm
            request.msd_req / float(topology.msd_limits.max()) # chain_norm
        ]
        return np.clip(obs, 0.0, 1.0)

_telemetry_ttl_raw = os.getenv("CORE_ROUTER_TELEMETRY_TTL_S")
_STATE_MANAGER = NetworkStateManager(
    max_telemetry_age_s=float(_telemetry_ttl_raw) if _telemetry_ttl_raw else None
)

def get_state_manager() -> NetworkStateManager:
    return _STATE_MANAGER
