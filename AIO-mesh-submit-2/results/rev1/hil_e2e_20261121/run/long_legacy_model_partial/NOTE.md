# Long run with legacy model — stopped early (partial, not used for claims)

Started 2026-11-21T18:21:24Z; stopped by operator 18:40Z (≈19 min) when the user asked
to rerun the long run with the corrected checkpoint instead of the legacy one.

Backend model during this run: results/models/v11/dgrl_v11_final_vietnam.zip
(sha256 42ea62747457807354611f72f21dcc3235eae60c93f2aa06e5a9e3e4cfd05d60, legacy,
pre-correction; normalizer 49e3075c…). The admission runner writes its summary only at
the end, so no admission results exist here; dataplane/ and kubernetes_readiness.csv hold
the rounds completed before the stop. One pending reservation the interrupted runner left
(vnf-data-dea19f2a, no Deployment) was released via /api/orchestrate/free:
release_interrupted_pending.json.
