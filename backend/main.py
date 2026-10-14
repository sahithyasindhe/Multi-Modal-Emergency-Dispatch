"""SENTINEL-911 FastAPI application entrypoint."""
from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.api.routes import DISCLAIMER, router
from backend.config import get_settings
from backend.database.models import init_db
from backend.rag.retriever import get_rag
from backend.utils.logging_utils import get_logger, setup_logging

setup_logging()
logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    init_db()
    rag = get_rag()
    logger.info(
        "SENTINEL-911 starting | mode=%s | rag=%s | %s",
        settings.model_mode,
        rag.status,
        DISCLAIMER,
    )
    yield
    logger.info("SENTINEL-911 shutdown")


app = FastAPI(
    title="SENTINEL-911 API",
    description=(
        "Autonomous Multi-Modal Emergency Dispatch & Triage Co-Pilot "
        "(RESEARCH/DEMO PROTOTYPE — not for real emergency use). "
        "AI recommends, human decides."
    ),
    version="1.0.0",
    lifespan=lifespan,
)

settings = get_settings()
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)


@app.get("/")
def root():
    return {
        "name": "SENTINEL-911",
        "status": "ok",
        "docs": "/docs",
        "disclaimer": DISCLAIMER,
    }
