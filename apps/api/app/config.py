"""Runtime configuration. Loaded from the environment."""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_env: str = "local"
    secret_key: str
    database_url: str
    redis_url: str
    smtp_host: str = "localhost"
    smtp_port: int = 1025
    smtp_from: str = "store@localhost"
    public_web_url: str = "http://localhost:3000"
    cors_origin: str = "http://localhost:3000"
    seed_admin_email: str = ""
    seed_admin_password: str = ""
    breach_check: str = "stub"
    phone_registration_enabled: bool = False
    sms_provider: str = "console"
    totp_encryption_key: str
    access_token_minutes: int = 15
    refresh_token_days: int = 14
    verification_minutes: int = 30
    reset_token_minutes: int = 30
    phone_otp_minutes: int = 5
    phone_otp_max_attempts: int = 5
    ticket_minutes: int = 5
    staff_invite_hours: int = 24
    login_rate_limit: int = 10
    login_rate_window_seconds: int = 60
    reset_rate_limit: int = 5
    reset_rate_window_seconds: int = 3600
    phone_rate_limit: int = 5
    phone_rate_window_seconds: int = 3600
    totp_rate_limit: int = 10
    totp_rate_window_seconds: int = 300


@lru_cache
def get_settings() -> Settings:
    # Fields are filled from the environment. The constructor call is valid at runtime.
    return Settings()  # type: ignore[call-arg]
