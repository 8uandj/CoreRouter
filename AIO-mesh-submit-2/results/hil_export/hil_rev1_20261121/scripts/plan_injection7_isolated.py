#!/usr/bin/env python3
"""Plan the todo-2 E6 fault-injection case: SID depth 7 on paths whose MSD-4 switch
must drop it, after the request itself was admitted at its real (in-limit) depth.

Admission and rules come from the real repository code (compile_pair_path,
compile_p4_forwarding_rules). The injected packet carries 7 SIDs: the admitted
path's SIDs at Segment List[0..d-1] plus already-traversed filler SIDs at
[d..6], with Segments Left = d-1, so it follows the installed rules until a
switch whose compiled MSD < 7 parses it. A paired control sends the normal
admitted-depth packet over the same installed path.

Usage: /home/CoreRouter/venv/bin/python scripts/plan_injection7_isolated.py <out_dir>
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import plan_overmsd_isolated as base  # noqa: E402

INJECT_DEPTH = 7


def main() -> int:
    out = Path(sys.argv[1]).resolve()
    out.mkdir(parents=True, exist_ok=False)
    msd = [float(x) for x in json.loads(base.RUN_MANIFEST.read_text())["msd_limits"]]
    profiles = {int(v): base.BUILD / "msd_{}".format(int(v)) / "srv6_msd_{}.json".format(int(v)) for v in set(msd)}
    plan = {"protocol": "isolated-bmv2-sid7-injection-v1", "created_utc": datetime.now(timezone.utc).isoformat(),
            "packets_per_trial": base.PACKETS_PER_TRIAL, "trials": base.TRIALS, "send_interval_s": base.SEND_INTERVAL_S,
            "msd_profile_by_node": msd,
            "profile_files": {str(k): {"file": str(v), "sha256": base.sha256(v)} for k, v in sorted(profiles.items())},
            "code_sha256": {
                "src/portal/backend/app/services/p4_pair_realization.py": base.sha256(base.REPO / "src/portal/backend/app/services/p4_pair_realization.py"),
                "infrastructure/sdn/p4_topology.py": base.sha256(base.REPO / "infrastructure/sdn/p4_topology.py")},
            "runs": []}
    cases = [
        ("depth4_path_s2-s1-s6-s7", 1, 6, 6, "admitted depth-4 path; MSD-4 switch s7 is the terminal"),
        ("depth2_path_s7-s6", 6, 5, 5, "admitted depth-2 path; MSD-4 switch s7 is the ingress"),
    ]
    for name, source, placement, route, purpose in cases:
        admitted = base.ppr.compile_pair_path(source, placement, route, requested_depth=len(base.ppr._shortest_path(source, placement)),
                                              route_msd_limit=msd[route], physical_msd_limits=msd)
        switch_path = list(admitted.switch_path)
        sids = list(admitted.sid_stack)
        ports = base.isolated_ports(switch_path)
        rules = base.compile_p4_forwarding_rules(switch_path, sids, ports)
        fillers = ["2001:db8:ffff::{}".format(i + 1) for i in range(INJECT_DEPTH - len(sids))]
        common = {"purpose": purpose, "request": {"source_node": source, "placement_node": placement, "route_node": route,
                                                   "requested_depth": len(sids)},
                  "node_path": list(admitted.node_path), "switch_path": switch_path, "sid_stack_final_to_first": sids,
                  "switch_msd": {"s%d" % s: msd[s - 1] for s in switch_path},
                  "switch_profile_file": {"s%d" % s: profiles[int(msd[s - 1])].name for s in switch_path},
                  "admission": {"decision": "admit", "error": None, "function": "compile_pair_path"},
                  "install_rules": True, "rules": rules, "rules_compiled_but_not_installed": [], "send_packets": True,
                  "port_map": {"{}|{}".format(*k): v for k, v in ports.items()}}
        plan["runs"].append(dict(common, case=name + "__control_admitted_depth", mode="admitted",
                                 expected_parser_drop_at=[]))
        plan["runs"].append(dict(common, case=name + "__injected_depth7", mode="fault_injection",
                                 packet_sid_list_final_to_first=sids + fillers,
                                 packet_segments_left=len(sids) - 1,
                                 expected_parser_drop_at=[("s%d" % s) for s in switch_path if INJECT_DEPTH > msd[s - 1]][:1]))
    (out / "plan.json").write_text(json.dumps(plan, indent=2))
    for r in plan["runs"]:
        print(r["case"], r["mode"], r["switch_path"], "packet depth", len(r.get("packet_sid_list_final_to_first") or r["sid_stack_final_to_first"]),
              "expected drop", r["expected_parser_drop_at"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
