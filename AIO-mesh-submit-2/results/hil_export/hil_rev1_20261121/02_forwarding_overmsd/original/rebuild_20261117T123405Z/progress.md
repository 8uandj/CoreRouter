# HIL 246 progress checkpoint

Updated: 2026-11-17
Repo: `/home/CoreRouter`
Run artifacts: `results/hil/rebuild_20261117T123405Z/`

## Goal and completion rule

Restore full HIL: admission → VNF create/readiness → P4 steering/forwarding → migration, with request-correlated Kubernetes/controller/packet/counter evidence. Do not report full HIL until all gates pass. The current 24-hour benchmark has not been started.

## Baseline state

- Seven recovered `vnf-attack-*` Deployments are Ready; the 43 retired Deployments are absent.
- Backend reports `reservation_persistence=durable`, zero `accounting_unknown`, and `unaccounted_vnfs=[]`.
- DGRL v11 is loaded.
- All 10 BMv2 Thrift ports are reachable.
- `phase10_backend_state.json`, `phase10_controller_health.json`, `phase10_deployments.txt`, and `phase10_services.txt` capture this state.
- Old Services remain for some retired workloads; no Service cleanup has been done in this phase.

## Source changes in this run

- `infrastructure/sdn/controller.py`: rule readback now compares BMv2 compact MAC parameters correctly when leading zeroes are omitted. Regression test in `tests/rev1/test_controller_rule_readback.py` failed before the change, then passed.
- `infrastructure/sdn/p4_topology.py` and `infrastructure/sdn/topo_p4.py`: P4 startup stops the passive Mininet OVS bridges while preserving interfaces for BMv2. It also replaces each Mininet host's K8s-subnet route through the configured bridge gateway instead of attempting a conflicting `ip route add`.
- Regression tests are in `tests/rev1/test_p4_bridge_detachment.py`.
- Verification run: `PYTHONPATH=. venv/bin/python tests/rev1/test_p4_bridge_detachment.py`, `...test_controller_rule_readback.py`, and `...test_p4_pair_realization.py` all pass; `git diff --check` passes. Full suite not run.

## Live topology and P4 state

- Current interactive Mininet process: `functions.exec_command` session ID `17644`; keep it alive.
- Its privileged helper container was `happy_heyrovsky` at last check; container name may change after restart.
- All 10 BMv2 were restarted after the source changes; controller bootstrap for all ten SIDs completed successfully.
- OVS bridge list is empty for this P4 topology. `s1-eth*`, `s6-eth*`, `s9-eth*` interfaces are UP and no longer enslaved to OVS.
- Exact smoke rules are installed from `phase13_path_rules.json`: s1 route `fc00:6::1/128` via port 4, s6 route `fc00:9::1/128` via port 5, s9 End.DX4 `fc00:9::1` via port 1. Controller bootstrap returned HTTP 200 `{"ok": true}`; source comparator independently confirms all three entries. These are temporary diagnostic rules, not yet admission-managed.
- Current smoke target is Ready Pod `10.1.189.159` (`vnf-attack-004e219d`, node worker2); this validates the existing P4 path only, not admission/create.
- `h9` Mininet namespace route was changed live to `10.1.0.0/16 via 10.1.240.1 dev veth-h9-mn`. It is a namespace route, not a host-global route. Source now uses `ip route replace` for all Mininet hosts on next restart.

## Packet evidence and current blocker

- Handcrafted one-packet SRv6/IPv4 ICMP smoke from h1 reached the P4 terminal action after OVS detachment; the first post-restart counter snapshot showed `srv6_advance_counter=1` on s1 and s6, and `srv6_terminal_counter=1` on s9, with zero MSD drops.
- No echo reply was observed. Host and h9-interface captures had zero matching packets. h9's route-to-Pod initially resolved directly on-link and neighbor state was FAILED; after namespace route replacement, `ip route get` showed gateway 10.1.240.1, but h9 capture still showed zero.
- One pre-fix test with OVS active caused high counter values (s1 advance 15, s6 advance 92, s9 terminal 385). Those rules were removed by exact BMv2 entry handles, and old switch counters were not reset. The new topology restart reset BMv2 runtime state.
- Current next investigation is only the final P4 output at s9 port 1 → h9-eth0 → veth-h9-mn → `br-k8s-mn` → Calico/Pod. Do not change host-global routes, bridge, firewall, or start broad traffic. P4 rules are exact and counters are in `phase13_s*_counters_checkpoint.txt`.
- `phase13_forward.pcap` and `phase13_h9_ingress.pcap` are capture artifacts; both have no matching frames. `phase13_send_srv6_icmp.py` records the packet construction. Capture command outputs are in the live transcript; record further commands/results in this directory.

## Next steps

1. Diagnose the s9 egress/Mininet host interface boundary with one packet and exact port counters; do not send a stream.
2. Once the packet is observed at h9 and then at the Pod, wire the validated live mapping into the backend admission realization and controller operation/readback; currently normal runtime still does not complete admission-to-P4 actuation.
3. Run one request-correlated create/readiness smoke, then one migration and over-MSD rejection; reconcile resources and ledger.
4. Only then consider bounded HIL experiments. Do not launch long benchmarks yet.

## Important untouched worktree state

There are pre-existing local modifications and untracked files across the repo. Do not reset, checkout, clean, commit, or overwrite them. Use `git status --short` before further edits.

## Latest continuation checkpoint (after Phase 14)

- User resumed the task and asked for a focused continuation plus durable context. This file is that context; preserve it and append new evidence rather than restarting the investigation.
- Regression tests now include both OVS detachment and replacement of the K8s route inside each Mininet namespace. The latter failed before helper implementation and now passes. Targeted controller and P4 path tests also pass.
- Live route on h9 was replaced with `10.1.0.0/16 via 10.1.240.1 dev veth-h9-mn`; `ip route get 10.1.189.159` now selects the gateway, but `ping` gets no reply.
- Three live P4 path entries remain installed from `phase13_path_rules.json`; controller bootstrap returned 200. Do not replace these with invented values; MACs are in the request and `phase13_live_p4_interfaces.txt`.
- Since the post-restart smoke, s1/s6 advance counters are 5 each and s9 terminal counter is 6; MSD violations remain zero (`phase14_s*_counters.txt`). This confirms packets reach the terminal action. Captures on h9 filtered by ICMP and by the configured MAC pair contain zero packets (`phase13_h9_ingress.pcap`, `phase14_h9_link.pcap`, `phase14_s9_port_return.pcap`). No echo reply was observed.
- BMv2 `show_ports` confirms s9 port 1 is `s9-eth1` and UP. Current P4 JSON for `srv6_end_dx4` assigns `standard_metadata.egress_spec=port`; table readback shows destination MAC `00:00:00:00:00:09`, source MAC `e2:39:34:f0:74:7e`, port 1. A direct terminal-SID packet incremented the terminal counter too, but h9's filtered capture remained empty.
- Current evidence localizes the unresolved issue after End.DX4 action execution and before a matching frame is observed at h9. Do not alter admission/backend, inventory, host-global routes, bridge, or firewall while diagnosing this single output boundary.
- The h9 namespace route correction is reversible and will disappear on topology restart; source applies it to all Mininet hosts on the next restart. No host-global route/bridge/firewall change was made by this continuation.

## Latest continuation checkpoint (Phase 16–19, 2026-11-17)

- Read-only `tc -s qdisc` snapshots for `s9-eth1`, `s6-eth5`, `s9-eth4`, and h9 `h9-eth0` show `dropped 0`, `overlimits 0`. Earlier large per-interface drop counters are not netem qdisc drops; no qdisc was changed.
- Recovered the correct shared checkout mount after one diagnostic command used the wrong path (`/home/CoreRouter` inside `chroot /host`); that failed run sent no packet and changed no live configuration. The shared workspace is `/host/home/CoreRouter` from the helper container.
- One exact-filter probe (ICMP id 246, seq 15) was captured at both `s9-eth1` and h9 `h9-eth0`, one frame at each. This proves the BMv2 terminal output reaches h9. Phase 17 captures: `phase17_s9_seq15.pcap`, `phase17_h9_seq15.pcap`.
- The same probe was captured at h9 `veth-h9-mn`, host peer `veth-h9-k8s`, and host `vxlan.calico`. Captured IPv4 TTLs are 64 at h9 egress, 63 at host bridge peer, and 62 on VXLAN egress; source `10.0.0.1`, destination `10.1.189.159`. This proves route/forwarding through the local host and out the Calico overlay. Phase 18–19 artifacts: `phase18_*`, `phase19_host_peer.pcap`, `phase19_vxlan.pcap` and logs.
- The current target Pod is Ready on worker2 at `10.1.189.159`, but its Deployment runs `alpine` with `sleep infinity` and has no listening TCP or UDP sockets. A failed ICMP echo therefore is not a valid application response check. `vnf-voc` is not currently deployed (only its old Service remains). The HIL smoke contract requires testing a real `vnf-voc` instance created through admission, not this placeholder.
- `core-router` currently has the seven retained `vnf-attack-*` Deployments Ready; their seven profile records remain as noted in Phase 1. No resource, route, firewall, qdisc, controller rule, or ledger mutation occurred in Phases 16–19. Temporary diagnostic P4 rules remain as before.
- Failed diagnostic invocation and exact output are in the interactive tool transcript; no packet was sent in that attempt. The successful captures and outputs are persisted in the phase files.

### Next gated work

1. Complete the request-specific source-backed admission realization implementation from the plan, using the live topology identity/interface evidence and exact operation-ID/controller-readback contract; targeted test-first changes only.
2. Create one new `vnf-voc` through the supported admission/Tekton path, correlate its Ready Pod and service endpoint, install the request's controller rules, and probe an actual application endpoint. Do not repurpose the sleeping baseline Deployment or claim it is an app-ready VNF.
3. Verify response/forwarding plus switch counter delta and one migration before bounded HIL runs.
