#!/usr/bin/env bash
set -euo pipefail

RUN=/home/CoreRouter/results/hil/rebuild_20261117T123405Z
OLD_NAME=bmv2-s1-prehil-20261117T123405Z
EXPECTED_ID=35546ab7932ccbda2e9270b5b8c481f237747d055ea183bf96c5c0b01df5577a
IMAGE_ID=sha256:44a5fcde557814dd5b3b2c400e7e2c0d34a7b19c3f8bcd1b891580ab89a63e53
CANDIDATE_DIR="$RUN/offline_p4_build/msd_10"
LOG="$RUN/phase9_canary_s1.log"
ROLLBACK_ARMED=0

rollback_s1() {
  set +e
  echo "CANARY_FAILED: restoring original s1 BMv2 container" | tee -a "$LOG"
  docker stop bmv2-s1 >>"$LOG" 2>&1
  docker rm bmv2-s1 >>"$LOG" 2>&1
  docker rename "$OLD_NAME" bmv2-s1 >>"$LOG" 2>&1
  docker start bmv2-s1 >>"$LOG" 2>&1
  for _ in $(seq 1 40); do
    if printf 'show_tables\n' | docker exec -i bmv2-s1 simple_switch_CLI --thrift-port 19091 >>"$LOG" 2>&1; then
      break
    fi
    sleep 1
  done
  printf 'table_add srv6_local_sid srv6_advance_segment fc00:1::1 =>\n' | docker exec -i bmv2-s1 simple_switch_CLI --thrift-port 19091 >>"$LOG" 2>&1
  printf 'table_dump srv6_local_sid\n' | docker exec -i bmv2-s1 simple_switch_CLI --thrift-port 19091 >>"$LOG" 2>&1
  ROLLBACK_ARMED=0
}
on_exit() {
  rc=$?
  if [[ "$rc" -ne 0 && "$ROLLBACK_ARMED" -eq 1 ]]; then rollback_s1; fi
  exit "$rc"
}
trap on_exit EXIT

current_id=$(docker inspect --format '{{.Id}}' bmv2-s1)
[[ "$current_id" == "$EXPECTED_ID" ]]
! docker inspect "$OLD_NAME" >/dev/null 2>&1
grep -q 'srv6_end_dx4_table' "$CANDIDATE_DIR/srv6_msd_10.p4info.txt"
grep -q 'srv6_advance_counter' "$CANDIDATE_DIR/srv6_msd_10.p4info.txt"
grep -q 'srv6_terminal_counter' "$CANDIDATE_DIR/srv6_msd_10.p4info.txt"
sha256sum "$CANDIDATE_DIR/srv6_msd_10.json" | tee -a "$LOG"

ROLLBACK_ARMED=1
docker stop bmv2-s1 | tee -a "$LOG"
docker rename bmv2-s1 "$OLD_NAME"
docker run -d --name bmv2-s1 --cpuset-cpus 2 --network host --privileged \
  -v "$CANDIDATE_DIR:/data:ro" --entrypoint simple_switch "$IMAGE_ID" \
  --device-id 1 --thrift-port 19091 --log-console --log-level warn \
  -i 1@s1-eth1 -i 2@s1-eth2 -i 3@s1-eth3 -i 4@s1-eth4 \
  /data/srv6_msd_10.json | tee -a "$LOG"

for _ in $(seq 1 40); do
  if printf 'show_tables\n' | docker exec -i bmv2-s1 simple_switch_CLI --thrift-port 19091 >"$RUN/phase9_canary_s1_ready.txt" 2>&1; then
    break
  fi
  sleep 1
done
grep -q 'srv6_end_dx4_table' "$RUN/phase9_canary_s1_ready.txt"
printf 'show_ports\n' | docker exec -i bmv2-s1 simple_switch_CLI --thrift-port 19091 >"$RUN/phase9_canary_s1_ports.txt"
printf 'table_dump srv6_local_sid\ntable_dump srv6_end_dx4_table\ntable_dump routing_v6\ncounter_read msd_violation_counter 0\ncounter_read srv6_advance_counter 0\ncounter_read srv6_terminal_counter 0\n' |
  docker exec -i bmv2-s1 simple_switch_CLI --thrift-port 19091 >"$RUN/phase9_canary_s1_readback.txt"
grep -q 's1-eth1.*UP' "$RUN/phase9_canary_s1_ports.txt"
grep -q 's1-eth2.*UP' "$RUN/phase9_canary_s1_ports.txt"
grep -q 's1-eth3.*UP' "$RUN/phase9_canary_s1_ports.txt"
grep -q 's1-eth4.*UP' "$RUN/phase9_canary_s1_ports.txt"
! grep -q 'Error:' "$RUN/phase9_canary_s1_readback.txt"
grep -q 'srv6_advance_counter\[0\].*packets=0' "$RUN/phase9_canary_s1_readback.txt"
grep -q 'srv6_terminal_counter\[0\].*packets=0' "$RUN/phase9_canary_s1_readback.txt"

# Restore the local-SID bootstrap entry present before the restart; keep route tables default-drop.
printf 'table_add srv6_local_sid srv6_advance_segment fc00:1::1 =>\n' |
  docker exec -i bmv2-s1 simple_switch_CLI --thrift-port 19091 >>"$LOG"
printf 'table_dump srv6_local_sid\n' | docker exec -i bmv2-s1 simple_switch_CLI --thrift-port 19091 >"$RUN/phase9_canary_s1_sid_readback.txt"
grep -q 'fc000001000000000000000000000001' "$RUN/phase9_canary_s1_sid_readback.txt"
docker inspect --format '{{.Id}} {{.Args}} {{.HostConfig.CpusetCpus}} {{json .Mounts}}' bmv2-s1 >"$RUN/phase9_canary_s1_inspect.txt"
echo "CANARY_PASS: s1 uses candidate MSD 10, expected tables/counters, all four original ports UP, bootstrap SID restored; route table remains empty/default-drop." | tee -a "$LOG"
ROLLBACK_ARMED=0
