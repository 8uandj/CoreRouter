from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from src.portal.backend.app.core.config import settings
from src.portal.backend.app.routers import api_v1, ai

app = FastAPI(title=settings.PROJECT_NAME, version=settings.VERSION)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_v1.router, prefix="/api")
app.include_router(ai.router, prefix="/api/ai")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("src.portal.backend.app.main:app", host="0.0.0.0", port=8000, reload=True)