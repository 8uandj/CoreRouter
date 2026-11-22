# Phase 9 — User-approved BMv2 reload, canary, and stop gate

The user approved restarting the ten BMv2 switches. Before restart, the fresh gate found the exact seven-name baseline, durable ledger with zero unknowns, API idle, no active PipelineRuns/Jobs, and all ten BMv2 containers up. Old JSON/P4Info files for MSD 4/5/8/10 and exact container IDs/args/mounts were saved under `phase9_live_p4_backup/` and `phase9_pre_restart/`.

## Canary s1

Restarted only s1 using the offline-compiled MSD 10 P4 JSON from this run directory. Kept the original container stopped as `bmv2-s1-prehil-20261117T123405Z`. The canary passed at that time:

- new `srv6_end_dx4_table`, `srv6_advance_counter`, and `srv6_terminal_counter` were present and readable;
- all four s1 interfaces were UP;
- counters were zero;
- the local SID bootstrap entry was reinstalled;
- route and End.DX4 tables had no forwarding entries and remained default-drop.

## Stop gate after tmux stop

The user then reported stopping the old `corerouter-p4` tmux session. Read-only inspection found no tmux server and controller REST `:8765` refused connections. Host attachment inspection found `br-k8s-mn` DOWN with address `10.1.240.1/16`, all existing `10.0.0.0/24` and `10.1.0.0/16` routes through it marked `linkdown`, and `veth-h1-k8s`–`veth-h10-k8s` absent. BMv2 `show_ports` reports port 1 DOWN on s1–s9; the backbone ports remain UP. s10 is stopped with exit 137 (OOM=false). The remaining switch reload script stopped in its preflight on:

```text
grep -q -- "s2-eth1.*UP" results/hil/rebuild_20261117T123405Z/phase9_s2_old_ports.txt
```

It returned status 1 because s2 port 1 was DOWN. **No switch after s1 was restarted.** The first script attempt also stopped before mutation on a parser bug; that transcript is preserved separately.

The missing/down Mininet host ports block VNF endpoint reachability. Do not restart the remaining switches or launch smoke. Restoring Mininet with `sudo /home/CoreRouter/venv/bin/python3 infrastructure/sdn/topo_p4.py --p4` would recreate host veth pairs, attach them to `br-k8s-mn`, set host IP forwarding and rp_filter, add FORWARD accept rules, and replace host routes for `10.0.0.0/24`. That remains outside the user's current authorization. The current state is therefore partial: s1 has the new P4 JSON, s2–s9 have old P4 JSON, s10 is exited; s1's host-facing port is now down; no forwarding routes have been installed.

## Safe next step

Choose a topology recovery method that restores Mininet host links and the controller without altering host bridges/routes/firewall, or explicitly authorize the specific host-level setup changes required by the existing `topo_p4.py`. After topology/controller recovery, recheck links and the seven-VNF baseline before deciding whether to resume the remaining BMv2 reloads. No forwarding, VNF create/readiness smoke, migration, or long HIL has passed.
