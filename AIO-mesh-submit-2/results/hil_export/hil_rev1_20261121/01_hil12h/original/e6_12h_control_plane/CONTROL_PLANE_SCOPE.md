# E6 12-hour control-plane HIL scope

This is the replacement run after the user changed the duration from 24 to 12
hours. It preserves the seven existing VNF Deployments and uses `--no-reset`.
The sequential `normal_load` client measures API outcomes, admission,
rejections, and any readiness observations exposed by the backend. A separate
read-only Kubernetes sampler records Deployment and Pod readiness every
minute.

The runner does not generate test packets or use packet forwarding to score
requests. Its controller status/MSD-counter reads are diagnostic preflight
fields only and are excluded from conclusions. Do not use this run to claim
packet latency/loss, forwarding stability, SRv6 delivery, or zero downtime.

The expected number of API calls at 3.5-second spacing is about 12,340 over
12 hours; the final raw record count and measured wall duration are authoritative.
The `normal_load` request factory skips some generated steps, so generated steps
must not be reported as API requests.
