"""Shared runtime configuration. Existing JO_VPPM_* names remain compatible."""

import os

os.environ.setdefault("JO_VPPM_ENABLE_MODEL", "1")
os.environ.setdefault("JO_VPPM_REQUIRE_MODEL", "1")
os.environ.setdefault("JO_VPPM_MODEL_PATH", "results/models/v11/dgrl_v11_final_vietnam.zip")
os.environ.setdefault("JO_VPPM_SCALER_PATH", "results/models/v11/vec_normalize_v11_vietnam.pkl")


class Settings:
    PROJECT_NAME: str = "AIO-Mesh / HARP Orchestrator"
    VERSION: str = "2.0.0"
    PROMETHEUS_URL: str = os.getenv("PROMETHEUS_URL", "http://localhost:9090")
    SDN_CONTROLLER_URL: str = os.getenv("SDN_CONTROLLER_URL", "http://localhost:8765")
    NAMESPACE: str = os.getenv("NAMESPACE", "core-router")
    VERTEX_PROJECT_ID: str = os.getenv("VERTEX_PROJECT_ID", "corerouter")
    VERTEX_LOCATION: str = os.getenv("VERTEX_LOCATION", "us-central1")
    VERTEX_ENDPOINT_ID: str = os.getenv("VERTEX_ENDPOINT_ID", "817138350065451008")


settings = Settings()
