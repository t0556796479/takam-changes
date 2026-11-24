"""FastAPI application. Run (from backend/):  uvicorn app.main:app --reload"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import router
from app.config import get_settings
from app.db import Base, engine


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title="Takam Changes API", version="0.1.0")
    app.add_middleware(CORSMiddleware, allow_origins=settings.cors_origins_list,
                       allow_methods=["*"], allow_headers=["*"])
    app.include_router(router)
    Base.metadata.create_all(engine)  # no-op when tables exist
    return app


app = create_app()
