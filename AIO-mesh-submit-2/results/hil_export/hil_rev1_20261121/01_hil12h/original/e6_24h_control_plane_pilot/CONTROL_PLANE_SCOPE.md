# E6 24-hour control-plane HIL scope

This run measures API request and admission outcomes, rejection reasons, and
Kubernetes deployment/readiness observations exposed by the backend.

It does not send test packets through P4. Controller status and MSD counters
may be sampled by the existing runner as preflight/diagnostic fields, but those
fields are excluded from the E6 conclusions. Do not use this run to claim
forwarding stability, packet latency, zero packet loss, zero downtime, or
verified SRv6 realization.

The runner must start with `--no-reset` because the control plane currently has
seven tracked VNF deployments. Existing reservations are outside the generated
trace and must not be cleared by this run. The selected `normal_load` workload
does not intentionally enable alerts or force migration. Deployment/readiness
counts therefore describe only operations naturally requested and observed by
the runtime during this workload; zero deployments is a valid outcome.

Request cadence: 3.5 seconds between API calls, targeting about 24,700 calls in
24 wall-clock hours. The actual completed request count and wall duration must
come from the raw records and run summary.
