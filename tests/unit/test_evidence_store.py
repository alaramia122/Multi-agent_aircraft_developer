"""Evidence references must remain verifiable across retries and corruption."""

from __future__ import annotations

from io import BytesIO
from typing import Any

import pytest
from botocore.exceptions import ClientError

from engineering_gateway.infrastructure.evidence_store import (
    EvidenceIntegrityError,
    EvidenceReference,
    S3EvidenceStore,
)


class FakeS3:
    def __init__(self) -> None:
        self.objects: dict[tuple[str, str], bytes] = {}

    def put_object(self, **kwargs: Any) -> dict[str, Any]:
        key = (kwargs["Bucket"], kwargs["Key"])
        assert kwargs["IfNoneMatch"] == "*"
        if key in self.objects:
            raise ClientError({"Error": {"Code": "PreconditionFailed"}}, "PutObject")
        self.objects[key] = kwargs["Body"]
        return {}

    def get_object(self, **kwargs: Any) -> dict[str, Any]:
        return {"Body": BytesIO(self.objects[(kwargs["Bucket"], kwargs["Key"])])}


def test_evidence_is_content_addressed_and_idempotent() -> None:
    client = FakeS3()
    store = S3EvidenceStore("engineering-evidence", client)
    first = store.put(b"signed verification result", media_type="text/plain", source_uri="git:abc123")
    repeated = store.put(b"signed verification result", media_type="text/plain", source_uri="git:abc123")
    assert first == repeated
    assert len(client.objects) == 1
    assert store.get_verified(first) == b"signed verification result"


def test_changed_data_at_existing_key_blocks_reuse_and_read() -> None:
    client = FakeS3()
    store = S3EvidenceStore("engineering-evidence", client)
    ref = store.put(b"original", media_type="text/plain", source_uri="git:abc123")
    client.objects[(ref.bucket, ref.key)] = b"altered!"
    with pytest.raises(EvidenceIntegrityError, match="altered"):
        store.get_verified(ref)
    with pytest.raises(EvidenceIntegrityError, match="altered"):
        store.put(b"original", media_type="text/plain", source_uri="git:abc123")


def test_reference_cannot_point_to_another_key_or_bucket() -> None:
    client = FakeS3()
    store = S3EvidenceStore("engineering-evidence", client)
    ref = store.put(b"evidence", media_type="text/plain", source_uri="git:abc123")
    wrong_key = EvidenceReference.model_validate({**ref.model_dump(), "key": "sha256/aa/" + "a" * 64})
    with pytest.raises(EvidenceIntegrityError, match="key"):
        store.get_verified(wrong_key)
    with pytest.raises(EvidenceIntegrityError, match="bucket"):
        store.get_verified(ref.model_copy(update={"bucket": "other"}))
