"""Centralised configuration — only place allowed to read environment variables."""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings


class WorkspaceConfig(BaseSettings):
    """Application configuration loaded from environment and .env file."""

    sop_workspace: Path = Path("SOP")
    """Root directory for all SOP runtime data. Override with SOP_WORKSPACE env var."""

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


@lru_cache(maxsize=1)
def get_config() -> WorkspaceConfig:
    """Return the singleton configuration instance."""
    return WorkspaceConfig()
