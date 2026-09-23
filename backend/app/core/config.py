"""
Application configuration, loaded from environment variables.
Per Master Requirements Section 36: no production secrets in .env in real
deployment (use a secret manager) — .env is for local development only.
"""
from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # App
    app_name: str = "Housing Society Management API"
    environment: str = "development"  # development | staging | production

    # Database
    database_url: str  # postgresql+asyncpg://user:pass@host:5432/dbname

    # Redis (cache, OTP, background jobs — Section 1)
    redis_url: str = "redis://localhost:6379/0"

    # Auth
    jwt_secret_key: str
    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_minutes: int = 30
    jwt_refresh_token_expire_days: int = 30

    # OTP
    otp_expiry_seconds: int = 300
    otp_length: int = 6

    # Push notifications (Section 1 / Section 30 — push_subscriptions)
    fcm_server_key: str | None = None
    web_push_vapid_public_key: str | None = None
    web_push_vapid_private_key: str | None = None

    # Payment proof uploads (Section 14.2/14.3) — local disk for now,
    # served back only via the authenticated GET /payments/{id}/proofs/
    # {proof_id}/file endpoint (no public StaticFiles mount — that was
    # removed as an audit fix, see upload_service.py); swap for object
    # storage (S3/GCS) in production without changing the upload_service
    # API.
    upload_dir: str = "uploads"


@lru_cache
def get_settings() -> Settings:
    return Settings()
