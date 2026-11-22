#!/usr/bin/env bash
set -euo pipefail
RUN=/home/CoreRouter/results/hil/rebuild_20261117T123405Z
SPECS="$RUN/phase9_pre_restart/container_runtime_specs.txt"
LOG="$RUN/phase9_reload_remaining.log"
IMAGE_ID=sha256:44a5fcde557814dd5b3b2c400e7e2c0d34a7b19c3f8bcd1b891580ab89a63e53
SWITCHES=(1)
ROLLBACK_ARMED=0

profile_for() {
  case "$1" in 1|2|9) echo 10 ;; 3|4|8|10) echo 5 ;; 5|7) echo 4 ;; 6) echo 8 ;; *) return 1 ;; esac
}
old_id_for() { awk -v name="/bmv2-s$1" '$1==name {print $2}' "$SPECS"; }
backup_name() { echo "bmv2-s$1-prehil-20261117T123405Z"; }
interfaces_for() {
  case "$1" in
    2) echo "-i 1@s2-eth1 -i 2@s2-eth2" ;;
    3) echo "-i 1@s3-eth1 -i 2@s3-eth2 -i 3@s3-eth3" ;;
    4) echo "-i 1@s4-eth1 -i 2@s4-eth2 -i 3@s4-eth3" ;;
    5) echo "-i 1@s5-eth1 -i 2@s5-eth2 -i 3@s5-eth3" ;;
    6) echo "-i 1@s6-eth1 -i 4@s6-eth4 -i 2@s6-eth2 -i 3@s6-eth3 -i 5@s6-eth5" ;;
    7) echo "-i 1@s7-eth1 -i 2@s7-eth2 -i 3@s7-eth3" ;;
    8) echo "-i 1@s8-eth1 -i 2@s8-eth2 -i 3@s8-eth3" ;;
    9) echo "-i 1@s9-eth1 -i 4@s9-eth4 -i 2@s9-eth2 -i 3@s9-eth3" ;;
    10) echo "-i 1@s10-eth1 -i 2@s10-eth2" ;;
  esac
}
rollback_all() {
  set +e
  echo "RELOAD_FAILED: rolling back all switches restarted in this operation, including canary s1" | tee -a "$LOG"
  for ((idx=${#SWITCHES[@]}-1; idx>=0; idx--)); do
    i=${SWITCHES[$idx]}; old=$(backup_name "$i"); port=$((19090+i))
    docker stop "bmv2-s$i" >>"$LOG" 2>&1
    docker rm "bmv2-s$i" >>"$LOG" 2>&1
    docker rename "$old" "bmv2-s$i" >>"$LOG" 2>&1
    docker start "bmv2-s$i" >>"$LOG" 2>&1
    for _ in $(seq 1 40); do
      if printf 'show_tables\n' | docker exec -i "bmv2-s$i" simple_switch_CLI --thrift-port "$port" >>"$LOG" 2>&1; then break; fi
      sleep 1
    done
    printf 'table_add srv6_local_sid srv6_advance_segment fc00:%x::1 =>\n' "$i" |
      docker exec -i "bmv2-s$i" simple_switch_CLI --thrift-port "$port" >>"$LOG" 2>&1
  done
  ROLLBACK_ARMED=0
}
on_exit() { rc=$?; if [[ "$rc" -ne 0 && "$ROLLBACK_ARMED" -eq 1 ]]; then rollback_all; fi; exit "$rc"; }
trap on_exit EXIT

[[ "$(docker inspect --format '{{.Id}}' bmv2-s1)" == "8dd3f63c8cd88dc77b7aa8af4e41fa773aa54184ca0c4746fb5f9a714d2019d2" ]]
[[ "$(docker inspect --format '{{.Id}}' bmv2-s1-prehil-20261117T123405Z)" == "$(old_id_for 1)" ]]
for i in $(seq 2 10); do
  [[ "$(docker inspect --format '{{.Id}}' "bmv2-s$i")" == "$(old_id_for "$i")" ]]
  ! docker inspect "$(backup_name "$i")" >/dev/null 2>&1
  profile=$(profile_for "$i"); candidate="$RUN/offline_p4_build/msd_${profile}"; port=$((19090+i))
  grep -q 'srv6_end_dx4_table' "$candidate/srv6_msd_${profile}.p4info.txt"
  grep -q 'srv6_advance_counter' "$candidate/srv6_msd_${profile}.p4info.txt"
  grep -q 'srv6_terminal_counter' "$candidate/srv6_msd_${profile}.p4info.txt"
  ifaces=$(interfaces_for "$i"); read -r -a iface_array <<<"$ifaces"
  ports_out="$RUN/phase9_s${i}_old_ports.txt"
  printf 'show_ports\ntable_dump routing_v6\n' | docker exec -i "bmv2-s$i" simple_switch_CLI --thrift-port "$port" >"$ports_out"
  ! grep -q 'Error:' "$ports_out"
  ! grep -q 'Dumping entry' "$ports_out"
  for ((j=1; j<${#iface_array[@]}; j+=2)); do grep -q -- "${iface_array[$j]#*@}.*UP" "$ports_out"; done
done
echo "PRECHECK_PASS: exact original container IDs, no route entries, expected live interfaces, and candidate P4Info verified." | tee -a "$LOG"

for i in $(seq 2 10); do
  profile=$(profile_for "$i"); candidate="$RUN/offline_p4_build/msd_${profile}"
  old=$(backup_name "$i"); port=$((19090+i)); cpuset=$((i+1)); ifaces=$(interfaces_for "$i")
  read -r -a iface_array <<<"$ifaces"
  SWITCHES+=("$i"); ROLLBACK_ARMED=1
  docker stop "bmv2-s$i" | tee -a "$LOG"
  docker rename "bmv2-s$i" "$old"
  docker run -d --name "bmv2-s$i" --cpuset-cpus "$cpuset" --network host --privileged \
    -v "$candidate:/data:ro" --entrypoint simple_switch "$IMAGE_ID" \
    --device-id "$i" --thrift-port "$port" --log-console --log-level warn \
    $ifaces "/data/srv6_msd_${profile}.json" | tee -a "$LOG"
  ready="$RUN/phase9_s${i}_tables.txt"
  for _ in $(seq 1 40); do
    if printf 'show_tables\n' | docker exec -i "bmv2-s$i" simple_switch_CLI --thrift-port "$port" >"$ready" 2>&1; then break; fi
    sleep 1
  done
  grep -q 'srv6_end_dx4_table' "$ready"
  readback="$RUN/phase9_s${i}_readback.txt"
  printf 'show_ports\ntable_dump srv6_local_sid\ntable_dump srv6_end_dx4_table\ntable_dump routing_v6\ncounter_read msd_violation_counter 0\ncounter_read srv6_advance_counter 0\ncounter_read srv6_terminal_counter 0\n' |
    docker exec -i "bmv2-s$i" simple_switch_CLI --thrift-port "$port" >"$readback"
  ! grep -q 'Error:' "$readback"
  ! grep -q 'Dumping entry' "$readback"
  for ((j=1; j<${#iface_array[@]}; j+=2)); do grep -q -- "${iface_array[$j]#*@}.*UP" "$readback"; done
  grep -q 'msd_violation_counter\[0\].*packets=0' "$readback"
  grep -q 'srv6_advance_counter\[0\].*packets=0' "$readback"
  grep -q 'srv6_terminal_counter\[0\].*packets=0' "$readback"
  printf 'table_add srv6_local_sid srv6_advance_segment fc00:%x::1 =>\n' "$i" |
    docker exec -i "bmv2-s$i" simple_switch_CLI --thrift-port "$port" >>"$LOG"
  sid_hex=$(python3 -c 'import ipaddress,sys; print(ipaddress.IPv6Address(sys.argv[1]).exploded.replace(":", ""))' "fc00:$i::1")
  sid_readback="$RUN/phase9_s${i}_sid_readback.txt"
  printf 'table_dump srv6_local_sid\n' | docker exec -i "bmv2-s$i" simple_switch_CLI --thrift-port "$port" >"$sid_readback"
  grep -q "$sid_hex" "$sid_readback"
  grep -q 'srv6_advance_segment' "$sid_readback"
  docker inspect --format '{{.Id}} {{.Args}} {{.HostConfig.CpusetCpus}} {{json .Mounts}}' "bmv2-s$i" >"$RUN/phase9_s${i}_inspect.txt"
  echo "RELOAD_PASS s$i MSD=$profile port=$port cpuset=$cpuset iface-list=$ifaces" | tee -a "$LOG"
done

for i in $(seq 1 10); do
  port=$((19090+i)); final="$RUN/phase9_s${i}_final_readback.txt"
  printf 'show_tables\ntable_dump srv6_local_sid\ntable_dump srv6_end_dx4_table\ntable_dump routing_v6\ncounter_read msd_violation_counter 0\ncounter_read srv6_advance_counter 0\ncounter_read srv6_terminal_counter 0\n' |
    docker exec -i "bmv2-s$i" simple_switch_CLI --thrift-port "$port" >"$final"
  grep -q 'srv6_end_dx4_table' "$final"
  grep -q 'srv6_advance_counter\[0\]' "$final"
  grep -q 'srv6_terminal_counter\[0\]' "$final"
  ! grep -q 'Error:' "$final"
done
echo "ALL_SWITCHES_P4_RELOAD_PASS: profiles match topology, new tables/counters read back on every switch; only per-node bootstrap SIDs installed; route and End.DX4 tables remain default-drop." | tee -a "$LOG"
ROLLBACK_ARMED=0
