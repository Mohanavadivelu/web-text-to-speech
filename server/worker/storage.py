"""Audio storage on Cloudflare R2 (or any S3-compatible store in development).

Objects are private; browsers download them through short-lived signed URLs.

    audio/users/<user id>/<job id>.mp3
    audio/anon/<anon id>/<job id>.mp3
"""

from __future__ import annotations

import logging
import re

import boto3
from botocore.config import Config
from botocore.exceptions import ClientError

from server.config import Settings

log = logging.getLogger(__name__)

_SAFE_ID = re.compile(r"^[A-Za-z0-9_-]{1,64}$")
CONTENT_TYPES = {"mp3": "audio/mpeg", "wav": "audio/wav"}


def audio_key(owner_kind: str, owner_id: str, job_id: str, fmt: str = "mp3") -> str:
    """Object key for a job's audio. IDs are checked so they can't escape their folder."""
    if owner_kind not in ("users", "anon"):
        raise ValueError(f"Unknown owner kind '{owner_kind}'.")
    for value in (owner_id, job_id):
        if not _SAFE_ID.match(value):
            raise ValueError(f"Unsafe id '{value}'.")
    if fmt not in CONTENT_TYPES:
        raise ValueError(f"Unknown format '{fmt}'.")
    return f"audio/{owner_kind}/{owner_id}/{job_id}.{fmt}"


class Storage:
    def __init__(self, settings: Settings):
        self.bucket = settings.r2_bucket
        self.ttl = settings.r2_signed_url_ttl_seconds
        self._client = self._make_client(settings, settings.storage_endpoint)
        # Signed URLs include the host, so they must be signed for the host browsers use
        self._signer = (
            self._client
            if settings.storage_public_endpoint == settings.storage_endpoint
            else self._make_client(settings, settings.storage_public_endpoint)
        )

    @staticmethod
    def _make_client(settings: Settings, endpoint: str):
        return boto3.client(
            "s3",
            endpoint_url=endpoint,
            aws_access_key_id=settings.r2_access_key_id,
            aws_secret_access_key=settings.r2_secret_access_key,
            region_name="auto",
            config=Config(
                signature_version="s3v4",
                s3={"addressing_style": "path"},
                retries={"max_attempts": 3, "mode": "standard"},
            ),
        )

    def ensure_bucket(self) -> None:
        """Create the bucket if it's missing (development stores only; R2 buckets exist already)."""
        try:
            self._client.head_bucket(Bucket=self.bucket)
        except ClientError:
            log.info("Creating bucket %s", self.bucket)
            self._client.create_bucket(Bucket=self.bucket)

    def put(self, key: str, data: bytes, content_type: str) -> None:
        self._client.put_object(Bucket=self.bucket, Key=key, Body=data, ContentType=content_type)

    def get(self, key: str) -> bytes:
        return self._client.get_object(Bucket=self.bucket, Key=key)["Body"].read()

    def exists(self, key: str) -> bool:
        try:
            self._client.head_object(Bucket=self.bucket, Key=key)
            return True
        except ClientError:
            return False

    def copy(self, source_key: str, dest_key: str) -> None:
        """Server-side copy (no download); used to reuse a cached result for a new owner."""
        self._client.copy_object(
            Bucket=self.bucket, Key=dest_key, CopySource={"Bucket": self.bucket, "Key": source_key}
        )

    def delete(self, key: str) -> None:
        self._client.delete_object(Bucket=self.bucket, Key=key)

    def signed_url(self, key: str, filename: str | None = None) -> str:
        params = {"Bucket": self.bucket, "Key": key}
        if filename:
            params["ResponseContentDisposition"] = f'attachment; filename="{filename}"'
        return self._signer.generate_presigned_url("get_object", Params=params, ExpiresIn=self.ttl)
