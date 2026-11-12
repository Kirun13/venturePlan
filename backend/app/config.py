from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field
from typing import Literal

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    database_url: str = "postgresql+asyncpg://venture:venture@localhost:5432/ventureplan"
    worker_poll_seconds: float = Field(default=1.0, gt=0)
    worker_lease_seconds: float = Field(default=600, gt=0)
    worker_max_attempts: int = Field(default=3, ge=1, le=20)
    worker_retry_base_seconds: float = Field(default=5, ge=0, le=3600)
    agent_mode: Literal["mock", "openai"] = "mock"
    openai_api_key: str | None = None
    openai_model: str = "gpt-4.1-mini"
    openai_web_search: bool = False
    openai_timeout: float = 90
    openai_max_retries: int = 2
    cors_origins: str = "http://localhost:3000,http://127.0.0.1:3000"
    session_hours: int = Field(default=168, ge=1, le=720)
    cookie_secure: bool = False
    generation_limit_hour: int = Field(default=20, ge=1)
    max_active_jobs: int = Field(default=3, ge=1)
    openai_max_output_tokens: int = Field(default=4000, ge=512, le=16000)

@lru_cache
def get_settings() -> Settings:
    return Settings()
