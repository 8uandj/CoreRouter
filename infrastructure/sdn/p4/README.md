# P4 SRv6 MSD checks

`tests/test_msd_enforcement.py` is an integration harness for a running,
isolated BMv2 switch. It sends an SID list longer than the loaded profile and
one exactly at the profile boundary. The over-depth packet must not appear on
the selected egress and must increment `msd_violation_counter`; the boundary
packet must appear on egress without incrementing that counter. The harness
records the loaded BMv2 JSON hash, P4 source hash, counter values, injected
packets, and captured egress packets.

Build the 4-SID profile with the P4 compiler container:

```bash
cd infrastructure/sdn/p4
make msd_4
cd ../../..
```

Run the harness as root on an isolated Mininet/BMv2 testbed. For switch `s1`,
the example assumes port 1 is `s1-eth1`, port 2 is `s1-eth2`, and its Thrift
port is 19091:

```bash
sudo python3 infrastructure/sdn/p4/tests/test_msd_enforcement.py \
  --container bmv2-s1 \
  --thrift-port 19091 \
  --ingress-iface s1-eth1 \
  --egress-iface s1-eth2 \
  --egress-port 2 \
  --msd 4 \
  --output results/p4_msd_run.json
```

The command requires Scapy on the host and Docker access. Use an isolated
switch because the test adds a unique IPv6 forwarding entry and expects no
unrelated traffic to increment the MSD counter during measurement. A passing
run demonstrates this behavior on that BMv2 software profile only. It does
not exercise controller admission, prove a parser-error log is exported, or
support claims about ASIC targets. The JSON records those evidence limits;
the admission result must be captured separately from the runtime API.
