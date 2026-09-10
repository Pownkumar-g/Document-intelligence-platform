"""Application configuration loaded from environment variables."""

import os
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings. All values can be overridden via environment variables."""

    GEMINI_API_KEY: str = ""
    DATABASE_URL: str = "sqlite:///./data/documents.db"
    LOG_LEVEL: str = "INFO"
    MAX_PAGES: int = 3
    MAX_FILE_SIZE_MB: int = 20
    APP_TITLE: str = "Document Intelligence Platform"
    APP_VERSION: str = "1.0.0"

    model_config = {
        "env_file": (".env", "backend/.env", "../.env"),
        "extra": "ignore",
    }


settings = Settings()
