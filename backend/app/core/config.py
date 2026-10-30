"""
Application configuration, loaded from environment variables.
Per Master Requirements Section 36: no production secrets in .env in real
deployment (use a secret manager) — .env is for local development only.
"""
from functools import lru_cache
from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # App
    app_name: str = "Housing Society Management API"
    environment: str = "development"  # development | staging | production

    # CORS
    cors_origins: list[str] | str = ["*"]

    # Database
    database_url: str  # postgresql+asyncpg://user:pass@host:5432/dbname

    @field_validator("database_url", mode="before")
    @classmethod
    def assemble_db_connection(cls, v: str) -> str:
        if isinstance(v, str):
            if v.startswith("postgres://"):
                return v.replace("postgres://", "postgresql+asyncpg://", 1)
            elif v.startswith("postgresql://") and not v.startswith("postgresql+asyncpg://"):
                return v.replace("postgresql://", "postgresql+asyncpg://", 1)
        return v

    @field_validator("cors_origins", mode="before")
    @classmethod
    def assemble_cors_origins(cls, v: list[str] | str) -> list[str]:
        if isinstance(v, str):
            return [origin.strip() for origin in v.split(",") if origin.strip()]
        return v

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

    # SMS (Twilio). Leave the account SID / auth token unset in local dev and
    # sms_service falls back to logging the OTP. Set twilio_messaging_service_sid
    # OR twilio_from_number (one is enough; the service SID wins if both are set).
    twilio_account_sid: str | None = None
    twilio_auth_token: str | None = None
    twilio_from_number: str | None = None  # E.164, e.g. +12025550123
    twilio_messaging_service_sid: str | None = None
    sms_default_country_code: str = "+91"  # prefixed to bare 10-digit mobiles

    # Push notifications (Section 1 / Section 30 — push_subscriptions)
    fcm_server_key: str | None = None
    web_push_vapid_public_key: str | None = None
    web_push_vapid_private_key: str | None = None

    # Shared secret for the (future, separately-built) Ecom store's
    # backend to call POST /wallet-redemptions/verify — a service-to-
    # service credential, never a Resident's own JWT, since the caller is
    # the store's server, not a logged-in person. None in local dev means
    # the endpoint is unreachable until an operator sets a real value.
    ecom_store_api_key: str | None = None

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
