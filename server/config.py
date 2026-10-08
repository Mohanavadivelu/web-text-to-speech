"""Settings shared by the API and the workers, read from environment variables and .env."""

from __future__ import annotations

from functools import lru_cache

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

DEV_COOKIE_SECRET = "dev-only-change-me"  # noqa: S105 (refused in production, see below)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_env: str = "development"
    log_level: str = "INFO"

    # Web
    public_web_origin: str = "http://localhost:5173"  # CORS; comma-separate several origins
    anon_cookie_secret: str = DEV_COOKIE_SECRET
    sentry_dsn: str = ""
    trust_cloudflare_ip_header: bool = False  # only behind Cloudflare (M6); otherwise spoofable

    # Accounts (Supabase)
    supabase_url: str = ""
    supabase_jwt_issuer: str = ""  # defaults to <supabase_url>/auth/v1
    database_url: str = ""
    turnstile_secret_key: str = ""  # empty = no bot check (development only)

    # Limits per tier (Stage 1 plan §10)
    anon_max_chars: int = 2000
    user_max_chars: int = 20_000
    anon_daily_chars: int = 10_000
    user_daily_chars: int = 100_000
    max_active_jobs: int = 2  # anonymous: running + queued
    user_max_active_jobs: int = 3
    rate_limit_per_minute: int = 10  # anonymous: job and file requests per IP
    user_rate_limit_per_minute: int = 30
    history_days: int = 7
    max_queued_jobs: int = 30  # per queue; above this new jobs get "busy"
    max_upload_bytes: int = 5 * 1024 * 1024
    extract_timeout_seconds: int = 20

    # Redis: job queue, live job events, cancel flags, rate limits
    redis_url: str = "redis://localhost:6379/0"

    # Object storage (Cloudflare R2 in production; any S3-compatible store in development)
    r2_account_id: str = ""
    r2_access_key_id: str = ""
    r2_secret_access_key: str = ""
    r2_bucket: str = "kokoro-tts-audio"
    r2_endpoint_url: str = ""  # override, e.g. http://seaweedfs:8333 in docker compose
    r2_public_endpoint_url: str = ""  # host that browsers use for signed links, if different
    r2_signed_url_ttl_seconds: int = 3600

    # Speech engine
    engine_threads: int = 0
    first_segment_chars: int = 150

    # Jobs: short texts get their own queue so they never wait behind long ones
    queue_short: str = "tts:short"
    queue_long: str = "tts:long"
    short_job_chars: int = 1000
    worker_queue: str = "tts:long"  # which queue this worker serves
    job_event_ttl_seconds: int = 600  # how long live events stay replayable
    job_record_ttl_seconds: int = 86_400
    min_job_timeout_seconds: int = 60
    cache_ttl_seconds: int = 20 * 3600  # shorter than the shortest audio lifetime (1 day)

    @model_validator(mode="after")
    def _no_dev_secrets_in_production(self) -> Settings:
        if self.app_env == "production":
            if self.anon_cookie_secret == DEV_COOKIE_SECRET:
                raise ValueError(
                    "ANON_COOKIE_SECRET must be set to a long random value in production."
                )
            if not self.turnstile_secret_key:
                raise ValueError("TURNSTILE_SECRET_KEY is required in production.")
        return self

    @property
    def jwt_issuer(self) -> str:
        return self.supabase_jwt_issuer or f"{self.supabase_url}/auth/v1"

    @property
    def storage_endpoint(self) -> str:
        if self.r2_endpoint_url:
            return self.r2_endpoint_url
        return f"https://{self.r2_account_id}.r2.cloudflarestorage.com"

    @property
    def storage_public_endpoint(self) -> str:
        return self.r2_public_endpoint_url or self.storage_endpoint


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
