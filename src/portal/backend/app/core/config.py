import os

class Settings:
    PROJECT_NAME: str = "3S-COM Orchestrator"
    VERSION: str = "2.0.0"
    PROMETHEUS_URL: str = os.getenv("PROMETHEUS_URL", "http://localhost:9090")
    os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = "gcp-key.json"
    VERTEX_PROJECT_ID: str = "corerouter"
    VERTEX_LOCATION: str = "us-central1" 
    VERTEX_ENDPOINT_ID: str = "817138350065451008"

settings = Settings()