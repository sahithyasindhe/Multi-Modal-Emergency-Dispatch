"""Application configuration via environment variables."""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(ROOT_DIR / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_env: str = "development"
    model_mode: Literal["demo", "hybrid", "full"] = "demo"
    openai_api_key: str = ""
    openai_base_url: str = "https://api.openai.com/v1"
    openai_model: str = "gpt-4o-mini"
    gemini_api_key: str = ""
    database_url: str = f"sqlite:///{ROOT_DIR / 'data' / 'sentinel.db'}"
    chroma_path: str = str(ROOT_DIR / "data" / "chroma")
    protocols_path: str = str(ROOT_DIR / "data" / "protocols")
    log_level: str = "INFO"
    log_raw_audio: bool = False
    persist_incidents: bool = True
    host: str = "0.0.0.0"
    port: int = 8000
    cors_origins: str = "*"
    dedup_time_window_minutes: int = 10
    dedup_distance_meters: float = 250.0
    dedup_similarity_threshold: float = 0.75
    max_revision_attempts: int = 2
    rag_top_k: int = 5
    rag_min_score: float = 0.15

    @property
    def root_dir(self) -> Path:
        return ROOT_DIR

    @property
    def demo_mode(self) -> bool:
        return self.model_mode == "demo" or not self.openai_api_key

    @property
    def cors_origin_list(self) -> list[str]:
        if self.cors_origins.strip() == "*":
            return ["*"]
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
