from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(".env.local", ".env"),
        env_file_encoding="utf-8",
        env_prefix="AI_SPRITE_",
        extra="ignore",
    )

    environment: str = Field(default="development", validation_alias="AI_SPRITE_ENV")
    api_host: str = "127.0.0.1"
    api_port: int = 8000
    workspace_dir: Path = Path("./workspace")
    database_url: str = "sqlite:///./data/ai_sprite_studio.db"
    comfyui_http_url: str = "http://127.0.0.1:8188"
    comfyui_ws_url: str = "ws://127.0.0.1:8188/ws"
    max_concurrent_ai_jobs: int = 1
    ai_timeout_seconds: int = 600


@lru_cache
def get_settings() -> Settings:
    return Settings()
