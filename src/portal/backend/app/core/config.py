import os

os.environ.setdefault("JO_VPPM_ENABLE_MODEL", "1")
os.environ.setdefault("JO_VPPM_REQUIRE_MODEL", "1")
os.environ.setdefault("JO_VPPM_MODEL_PATH", "results/models/v11/dgrl_v11_final_vietnam.zip")
os.environ.setdefault("JO_VPPM_SCALER_PATH", "results/models/v11/vec_normalize_v11_vietnam.pkl")

class Settings:
    PROJECT_NAME: str = "3S-COM Orchestrator - INTEGRATED"
    VERSION: str = "2.0.0"
    PROMETHEUS_URL: str = os.getenv("PROMETHEUS_URL", "http://localhost:9090")
    SDN_CONTROLLER_URL: str = os.getenv("SDN_CONTROLLER_URL", "http://localhost:8765")
    os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = "gcp-key.json"
    VERTEX_PROJECT_ID: str = "corerouter"
    VERTEX_LOCATION: str = "us-central1" 
    VERTEX_ENDPOINT_ID: str = "817138350065451008"

settings = Settings()
