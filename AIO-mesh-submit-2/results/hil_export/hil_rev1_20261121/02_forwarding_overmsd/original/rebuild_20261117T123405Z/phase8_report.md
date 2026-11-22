# Phase 8 — Live P4 realization gate

Captured 2026-11-17 on host `3s-com`, repository `/home/CoreRouter`, branch `HARP`, commit `7f4a5eb50a938a0540906df32c9c4940a54e803f`.

## Gate result

**Phase 0, 1, 2 and 4 pass from the retained run artifacts and refreshed snapshot. Phase 3 live P4 realization fails. Phases 5 and 6 were not started.**

The refreshed Kubernetes/API snapshot has exactly seven Deployments, all seven available and Ready; all seven names are the approved keep list. None of the 43 retirement names is present. There are no active PipelineRuns, Jobs, migrations or HIL Python processes. The backend reports `System Idle`, `reservation_persistence=durable`, seven active records, zero `accounting_unknown`, and `unaccounted_vnfs=[]`.

## Exact live P4 mismatch

All ten BMv2 processes use the topology's expected per-switch MSD profile mapping:

```text
s1,s2,s9=10; s3,s4,s8,s10=5; s5,s7=4; s6=8
```

The per-node mounts point to the matching `build/msd_N` directory read-only. The *loaded JSON in each profile is still the old program*: `show_tables` lists `routing_v6` and `srv6_local_sid`, but no terminal `srv6_end_dx4_table`. For each of s1–s10, the exact read-only command included:

```text
table_dump srv6_end_dx4_table
```

and returned:

```text
Error: Invalid table name (srv6_end_dx4_table)
```

`counter_read msd_violation_counter 0` succeeds at 0. Both `counter_read srv6_advance_counter 0` and `counter_read srv6_terminal_counter 0` return `Invalid counter name`. The existing local-SID bootstrap rule is present; `routing_v6` is empty and defaults to drop. No live forwarding packet was observed.

The modified P4 source compiles offline for MSD 4/5/8/10. An isolated two-switch BMv2 test passes one RFC 8754 packet through segment advance and End.DX4, with packet capture and advance/terminal counter deltas; its over-MSD packet is dropped with the violation counter incremented. The compiled files and packet captures are preserved here. This does not prove that the running 246 switches loaded that P4 program or that their port/VNF endpoint mapping is correct. An initial Phase 8 note inferred the s1 profile for all ten switches; the per-container Phase 9 inspection corrected that note and confirmed the expected profile selection.

## Focused verification

```text
python3 -m unittest tests.rev1.test_controller_rule_readback tests.rev1.test_p4_pair_realization infrastructure.sdn.p4.tests.test_srv6_realization_contract -v
Ran 15 tests — OK
git diff --check — pass
```

## Next safe step

Do not run the VNF create/readiness, steering, migration smoke or long HIL while this mismatch remains. The approved next operation is a canary restart of s1 with the reviewed MSD 10 build, then profile/table/counter readback. If it passes, restart the remaining nine using their observed interface/CPU/Thrift settings. Keep the old JSON files and stopped containers as rollback evidence. Before smoke, verify actual switch ports/MACs, K8s endpoint reachability, readback and packet counters.

**Current conclusion: baseline rebuilt; full HIL blocked.**
