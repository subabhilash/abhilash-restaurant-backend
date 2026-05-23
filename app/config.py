from functools import lru_cache
from typing import Optional
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # ── App ────────────────────────────────────────────────────────────────────
    app_env: str = "development"
    debug: bool = False

    # ── Database ───────────────────────────────────────────────────────────────
    database_url: str

    # ── JWT ────────────────────────────────────────────────────────────────────
    jwt_secret_key: str
    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_minutes: int = 15
    jwt_refresh_token_expire_days: int = 7

    # ── Cookies ────────────────────────────────────────────────────────────────
    # Set True in production (requires HTTPS).
    # False for local development (HTTP is fine on localhost).
    cookie_secure: bool = False

    # ── CORS ───────────────────────────────────────────────────────────────────
    cors_origins: str = "http://localhost:3000"

    # ── Frontend ───────────────────────────────────────────────────────────────
    frontend_url: str = "http://localhost:3000"

    # ── Email (Resend) ─────────────────────────────────────────────────────────
    resend_api_key: str = ""
    resend_from_email: str = "noreply@yourdomain.com"

    # ── Logging ────────────────────────────────────────────────────────────────
    log_level: str = "info"

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def is_production(self) -> bool:
        return self.app_env == "production"


@lru_cache
def get_settings() -> Settings:
    return Settings()
