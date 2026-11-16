import os
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    PROJECT_NAME: str = "3S-COM Orchestrator"
    VERSION: str = "2.0.0"
    PROMETHEUS_URL: str = os.getenv("PROMETHEUS_URL", "http://localhost:9090")
    
    # K8s Config
    NAMESPACE: str = "vnf"
    
    # Vertx AI (Placeholder from old config)
    VERTEX_PROJECT_ID: str = "corerouter"
    VERTEX_LOCATION: str = "us-central1"
    VERTEX_ENDPOINT_ID: str = "817138350065451008"

    class Config:
        case_sensitive = True

settings = Settings()
