"""
Central configuration — loads from .env, single source of truth.
"""
from __future__ import annotations
from pydantic_settings import BaseSettings
from typing import Literal
from functools import lru_cache


class Settings(BaseSettings):
    # ── LLM ──
    google_gemini_api_key: str = ""
    openai_api_key: str = ""
    default_llm_provider: Literal["gemini", "openai"] = "gemini"
    gemini_model: str = "gemini-2.5-flash"
    gemini_vision_model: str = "gemini-2.5-flash"
    openai_model: str = "gpt-4o"

    # ── Database ──
    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/lc_platform"
    database_url_sync: str = "postgresql+psycopg2://postgres:postgres@localhost:5432/lc_platform"

    # ── External APIs ──
    perplexity_api_key: str = ""
    perplexity_model: str = "sonar-pro"
    exa_api_key: str = ""
    api_ninjas_key: str = ""
    api_ninjas_premium: bool = False
    geoapify_key: str = ""
    unlocode_csv_path: str = ""

    # ── App ──
    app_language: str = "en"
    app_log_level: str = "INFO"
    app_host: str = "0.0.0.0"
    app_port: int = 8000
    mcp_port: int = 8100
    app_secret_key: str = "change-this-in-production"

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8", "extra": "ignore"}

    @property
    def has_gemini(self) -> bool:
        return bool(self.google_gemini_api_key)

    @property
    def has_openai(self) -> bool:
        return bool(self.openai_api_key)


@lru_cache()
def get_settings() -> Settings:
    return Settings()


# Constants
GEMINI_MODELS = [
    "gemini-2.5-flash", "gemini-2.5-pro", "gemini-2.0-flash",
    "gemini-2.0-flash-lite", "gemini-1.5-pro", "gemini-1.5-flash",
]
SUPPORTED_LANGUAGES = ["en", "ar", "es", "it"]
MAX_PDF_TEXT_FOR_LLM = 15000
MAX_VISION_PAGES = 15
