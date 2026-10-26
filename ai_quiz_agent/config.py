"""
config.py
---------
Centralised configuration for the AI Quiz Agent system.

Handles:
- Loading environment variables from .env (never hardcode secrets)
- Building a lazily-initialised OpenAI client
- Small tunables (model name, retry limits, chunk sizes) in one place

This module has NO dependency on Jupyter and can be imported directly
by a future FastAPI app without changes.
"""

from __future__ import annotations

import os
from pathlib import Path
from functools import lru_cache

from dotenv import load_dotenv

# Load variables from a .env file if present. Safe to call multiple times.
load_dotenv(Path(__file__).resolve().parent / ".env")
load_dotenv(Path(__file__).resolve().parent.parent / ".env")


class ConfigError(Exception):
    """Raised when required configuration (e.g. API key) is missing."""


class Settings:
    """Simple settings object. In FastAPI this could become a pydantic-settings class."""

    OPENAI_API_KEY: str | None = os.getenv("OPENAI_API_KEY")
    OPENAI_MODEL: str = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

    # Cost-control / chunking
    MAX_CONTENT_CHARS: int = int(os.getenv("MAX_CONTENT_CHARS", "12000"))
    CHUNK_SIZE_CHARS: int = int(os.getenv("CHUNK_SIZE_CHARS", "6000"))
    CHUNK_OVERLAP_CHARS: int = int(os.getenv("CHUNK_OVERLAP_CHARS", "300"))

    # AI agent retry limits
    MAX_GENERATION_RETRIES: int = int(os.getenv("MAX_GENERATION_RETRIES", "3"))
    MAX_ANALYSIS_RETRIES: int = int(os.getenv("MAX_ANALYSIS_RETRIES", "3"))

    # Minimum characters required for content to be considered valid study material
    MIN_CONTENT_CHARS: int = int(os.getenv("MIN_CONTENT_CHARS", "200"))


settings = Settings()


@lru_cache(maxsize=1)
def get_openai_client():
    """
    Lazily build and cache an OpenAI client.

    Raises ConfigError with a clear message if the API key is missing,
    rather than letting the program crash with an unclear stack trace.
    """
    if not settings.OPENAI_API_KEY:
        raise ConfigError(
            "OPENAI_API_KEY is not set. Create a .env file in the project root "
            "with a line like: OPENAI_API_KEY=sk-... "
            "Never hardcode the key in source code."
        )

    # Imported here so that importing config.py doesn't require the openai
    # package to be installed unless a client is actually requested.
    from openai import OpenAI

    return OpenAI(api_key=settings.OPENAI_API_KEY)
