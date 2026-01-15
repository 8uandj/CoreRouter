from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings
from app.routers import api_v1, ai

app = FastAPI(title=settings.PROJECT_NAME, version=settings.VERSION)

# Cấu hình CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Đăng ký Router (Gom tất cả API vào /api)
app.include_router(api_v1.router, prefix="/api")
app.include_router(ai.router, prefix="/api/ai")
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)