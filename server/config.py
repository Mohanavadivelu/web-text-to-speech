"""Settings shared by the API and the workers, read from environment variables and .env."""

from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_env: str = "development"
    log_level: str = "INFO"

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

    # Jobs
    job_event_ttl_seconds: int = 600  # how long live events stay replayable
    job_record_ttl_seconds: int = 86_400
    min_job_timeout_seconds: int = 60

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
