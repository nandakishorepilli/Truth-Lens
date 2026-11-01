"""FastAPI application entrypoint for TruthLens."""
from __future__ import annotations

from contextlib import asynccontextmanager
import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import router as api_router
from app.core.config import load_env_file, parse_origins
from app.db.session import init_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan context: initialize database on startup."""
    init_db()
    yield


def create_app() -> FastAPI:
    """Create and configure the FastAPI application instance."""
    load_env_file("backend/.env")
    load_env_file(".env")

    application = FastAPI(
        title="TruthLens API",
        version="0.1.0",
        description="Factual verification API measuring AI answer support against evidence.",
        lifespan=lifespan,
    )

    cors_env = os.environ.get("CORS_ALLOWED_ORIGINS", "http://localhost:5173")
    origins = parse_origins(cors_env)
    if origins:
        application.add_middleware(
            CORSMiddleware,
            allow_origins=origins,
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

    application.include_router(api_router, prefix="/api")
    return application


app = create_app()
