#!/usr/bin/env python3
"""Plan the controlled protected/bypass over-MSD comparison (control plane only).

Runs the repository's real admission/path code offline, with no network access:
  * src/portal/backend/app/services/p4_pair_realization.compile_pair_path
    (protected admission: exact depth, route-profile and per-switch MSD checks)
  * p4_pair_realization._shortest_path + RFC 8754 reversal (bypass: same path and
    SID stack, MSD checks skipped)
  * infrastructure/sdn/p4_topology.compile_p4_forwarding_rules (controller rules)
The P4 switch profiles are the Vietnam per-node MSD values recorded in the 12-h
HIL run manifest, and the compiled BMv2 JSON for each switch is selected by
that value from the offline build whose hashes equal the live switches.

Output: <out>/plan.json consumed by exec_overmsd_isolated.py inside a disposable
network-less container. Usage:
  /home/CoreRouter/venv/bin/python scripts/plan_overmsd_isolated.py <out_dir>
"""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO = Path("/home/CoreRouter")
sys.path.insert(0, str(REPO))
from infrastructure.sdn.p4_topology import P4_NODE_COUNT, compile_p4_forwarding_rules  # noqa: E402
from src.portal.backend.app.services import p4_pair_realization as ppr  # noqa: E402

BUILD = REPO / "results/hil/rebuild_20261117T123405Z/offline_p4_build"
RUN_MANIFEST = REPO / "results/rev1/e6_12h_control_plane/runs/20261117_190242/run_manifest.json"
PACKETS_PER_TRIAL = 100
TRIALS = 3
SEND_INTERVAL_S = 0.01


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def mac(switch: int, port: int) -> str:
    return "02:00:00:00:{:02x}:{:02x}".format(switch, port)


def isolated_ports(switch_path):
    """Port map for a linear isolated chain: port 1 faces ingress, port 2 egress."""
    ports = {}
    for a, b in zip(switch_path, switch_path[1:]):
        ports[("s%d" % a, "s%d" % b)] = {"out_port": 2, "src_mac": mac(a, 2), "dst_mac": mac(b, 1)}
    last = switch_path[-1]
    ports[("s%d" % last, "host")] = {"out_port": 2, "src_mac": mac(last, 2), "dst_mac": "02:00:00:00:00:02"}
    return ports


def main() -> int:
    out = Path(sys.argv[1]).resolve()
    out.mkdir(parents=True, exist_ok=True)
    msd = [float(x) for x in json.loads(RUN_MANIFEST.read_text())["msd_limits"]]
    profiles = {int(v): BUILD / "msd_{}".format(int(v)) / "srv6_msd_{}.json".format(int(v)) for v in set(msd)}

    # Enumerate every ordered (source, placement) pair to document which
    # requests are physically over-MSD on this topology.
    pair_table = []
    for s in range(P4_NODE_COUNT):
        for p in range(P4_NODE_COUNT):
            if s == p:
                continue
            path = ppr._shortest_path(s, p)
            depth = len(path)
            violators = ["s%d" % (n + 1) for n in path if depth > msd[n]]
            pair_table.append({"source": s, "placement": p, "node_path": list(path),
                               "depth": depth, "switch_msd": [msd[n] for n in path],
                               "over_msd_switches": violators})

    cases = [
        # name, source, placement, route node, purpose
        ("in_limit_depth2", 5, 6, 6, "adjacent pair; the only depth admitted in the 12-h HIL run"),
        ("in_limit_depth4_at_msd4", 1, 6, 6, "depth equals the MSD-4 terminal switch limit"),
        ("over_msd_depth5", 1, 7, 7, "depth 5 crosses s7 (MSD 4); route-profile limit (s8, MSD 5) passes"),
    ]
    plan = {"protocol": "isolated-bmv2-overmsd-protected-bypass-v2",
            "created_utc": datetime.now(timezone.utc).isoformat(),
            "packets_per_trial": PACKETS_PER_TRIAL, "trials": TRIALS,
            "send_interval_s": SEND_INTERVAL_S,
            "msd_profile_by_node": msd,
            "profile_files": {str(k): {"file": str(v), "sha256": sha256(v)} for k, v in sorted(profiles.items())},
            "code_sha256": {
                "src/portal/backend/app/services/p4_pair_realization.py": sha256(REPO / "src/portal/backend/app/services/p4_pair_realization.py"),
                "infrastructure/sdn/p4_topology.py": sha256(REPO / "infrastructure/sdn/p4_topology.py"),
                "infrastructure/sdn/p4/srv6_basic.p4": sha256(REPO / "infrastructure/sdn/p4/srv6_basic.p4"),
                "run_manifest.json(msd source)": sha256(RUN_MANIFEST),
            },
            "pair_depth_table": pair_table,
            "runs": []}

    for name, source, placement, route, purpose in cases:
        node_path = ppr._shortest_path(source, placement)
        switch_path = [n + 1 for n in node_path]
        sid_stack = ["fc00:{}::1".format(n + 1) for n in reversed(node_path)]
        depth = len(sid_stack)
        # protected admission: the real backend function
        try:
            t0 = datetime.now(timezone.utc)
            admitted_path = ppr.compile_pair_path(
                source, placement, route, requested_depth=depth,
                route_msd_limit=msd[route], physical_msd_limits=msd)
            protected = {"decision": "admit", "error": None,
                         "sid_stack": list(admitted_path.sid_stack),
                         "switch_path": list(admitted_path.switch_path)}
        except ValueError as exc:
            protected = {"decision": "reject", "error": str(exc)}
        protected["decided_utc"] = t0.isoformat()
        ports = isolated_ports(switch_path)
        rules = compile_p4_forwarding_rules(switch_path, sid_stack, ports)
        for mode in ("protected", "bypass"):
            if mode == "protected":
                install = protected["decision"] == "admit"
                admission = protected
            else:
                install = True
                admission = {"decision": "bypassed", "error": None,
                             "note": "MSD/depth admission predicates skipped; same path and SID stack"}
            plan["runs"].append({
                "case": name, "mode": mode, "purpose": purpose,
                "request": {"source_node": source, "placement_node": placement, "route_node": route,
                            "requested_depth": depth},
                "node_path": list(node_path), "switch_path": switch_path, "sid_stack_final_to_first": sid_stack,
                "switch_msd": {"s%d" % s: msd[s - 1] for s in switch_path},
                "switch_profile_file": {"s%d" % s: profiles[int(msd[s - 1])].name for s in switch_path},
                "expected_parser_drop_at": [("s%d" % s) for s in switch_path if depth > msd[s - 1]][:1],
                "admission": admission,
                "install_rules": install,
                "rules": rules if install else [],
                "rules_compiled_but_not_installed": [] if install else rules,
                "send_packets": install,
                "port_map": {"{}|{}".format(*k): v for k, v in ports.items()},
            })
    (out / "plan.json").write_text(json.dumps(plan, indent=2))
    print(json.dumps([dict({k: r[k] for k in ("case", "mode", "install_rules")}, **{
        "decision": r["admission"]["decision"], "error": r["admission"].get("error"),
        "switch_path": r["switch_path"], "drop_at": r["expected_parser_drop_at"]}) for r in plan["runs"]], indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
