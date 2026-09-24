"""Content-addressed evidence in an S3-compatible authoritative object store.

The Gateway records references and digests, not copies of engineering artifacts.
Writes use a conditional S3 PutObject, and every read checks the digest again.
"""

from __future__ import annotations

import hashlib
from typing import Any, Protocol

import boto3  # type: ignore[import-untyped]
from botocore.config import Config  # type: ignore[import-untyped]
from botocore.exceptions import ClientError  # type: ignore[import-untyped]
from pydantic import BaseModel, ConfigDict, Field

from engineering_gateway.config import ObjectStorageConfig


class EvidenceIntegrityError(RuntimeError):
    """The stored data does not match its immutable evidence reference."""


class EvidenceReference(BaseModel):
    """Portable provenance and integrity reference to external binary evidence."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    bucket: str = Field(min_length=1)
    key: str = Field(pattern=r"^sha256/[0-9a-f]{2}/[0-9a-f]{64}$")
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    size_bytes: int = Field(ge=0)
    media_type: str = Field(min_length=1)
    source_uri: str = Field(min_length=1)


class S3Client(Protocol):
    def put_object(self, **kwargs: Any) -> dict[str, Any]: ...
    def get_object(self, **kwargs: Any) -> dict[str, Any]: ...


class S3EvidenceStore:
    """Atomic create-only objects with verified reads and repeatable references."""

    def __init__(self, bucket: str, client: S3Client):
        if not bucket:
            raise ValueError("evidence bucket is required")
        self.bucket = bucket
        self._client = client

    def put(self, data: bytes, *, media_type: str, source_uri: str) -> EvidenceReference:
        if not media_type or not source_uri:
            raise ValueError("media_type and source_uri are required for evidence provenance")
        digest = hashlib.sha256(data).hexdigest()
        reference = EvidenceReference(
            bucket=self.bucket,
            key=f"sha256/{digest[:2]}/{digest}",
            sha256=digest,
            size_bytes=len(data),
            media_type=media_type,
            source_uri=source_uri,
        )
        try:
            self._client.put_object(
                Bucket=self.bucket,
                Key=reference.key,
                Body=data,
                ContentType=media_type,
                Metadata={"sha256": digest},
                IfNoneMatch="*",
            )
        except ClientError as exc:
            code = str(exc.response.get("Error", {}).get("Code", ""))
            if code not in {"412", "PreconditionFailed", "409", "ConditionalRequestConflict"}:
                raise
            # An existing key is safe to reuse only after verifying its bytes.
            self.get_verified(reference)
        return reference

    def get_verified(self, reference: EvidenceReference) -> bytes:
        if reference.bucket != self.bucket:
            raise EvidenceIntegrityError("evidence bucket does not match configuration")
        if reference.key != f"sha256/{reference.sha256[:2]}/{reference.sha256}":
            raise EvidenceIntegrityError("evidence key does not match digest")
        response = self._client.get_object(Bucket=self.bucket, Key=reference.key)
        body: bytes = response["Body"].read()
        if len(body) != reference.size_bytes or hashlib.sha256(body).hexdigest() != reference.sha256:
            raise EvidenceIntegrityError("object storage returned altered evidence")
        return body


def configured_evidence_store(config: ObjectStorageConfig) -> S3EvidenceStore | None:
    """Build the integration only for an explicitly enabled S3 backend."""

    if not config.enabled:
        return None
    assert config.endpoint_url and config.bucket
    assert config.access_key_id and config.secret_access_key
    client = boto3.client(
        "s3",
        endpoint_url=config.endpoint_url,
        region_name=config.region,
        aws_access_key_id=config.access_key_id.get_secret_value(),
        aws_secret_access_key=config.secret_access_key.get_secret_value(),
        config=Config(s3={"addressing_style": "path"}, connect_timeout=config.connect_timeout_seconds),
    )
    return S3EvidenceStore(config.bucket, client)
