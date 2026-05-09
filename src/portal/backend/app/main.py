from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from src.portal.backend.app.core.config import settings
from src.portal.backend.app.routers import ai, api_v1, migrate, orchestration_router
from src.ai.dgrl_agent import get_dgrl_agent

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Warm-up AI Model
    print("AI Model Warm-up: Loading JO-VPPM model into RAM...")
    get_dgrl_agent()._load_model()
    yield

app = FastAPI(
    title=settings.PROJECT_NAME, 
    version=settings.VERSION,
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_v1.router, prefix="/api")
app.include_router(ai.router, prefix="/api/ai")
app.include_router(orchestration_router.router, prefix="/api")
app.include_router(migrate.router, prefix="/api")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("src.portal.backend.app.main:app", host="0.0.0.0", port=8000, reload=True)
