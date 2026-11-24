"""Central configuration, read from environment variables / .env.

Every tunable value lives here (not in the code), so the same code runs
locally, in tests and in production with different settings.
"""
from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parent.parent
PROJECT_DIR = BACKEND_DIR.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(PROJECT_DIR / ".env", BACKEND_DIR / ".env"), extra="ignore"
    )

    data_dir: Path = PROJECT_DIR / "data"
    database_url: str = f"sqlite:///{BACKEND_DIR / 'takam.db'}"

    ai_provider: str = "none"          # "none" | "anthropic"
    anthropic_api_key: str = ""
    ai_model: str = "claude-opus-5-5"

    # Comma separated origins allowed to call the API from a browser (the React dev server).
    cors_origins: str = "http://localhost:5173"

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
