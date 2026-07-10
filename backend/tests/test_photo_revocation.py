"""Storage fault coverage for fail-closed photo revocation."""

from __future__ import annotations

import hashlib
from datetime import datetime

import pytest

from app.core.storage import StorageCopyVerificationError, StorageObjectProperties
from app.moderation.revocation import ClaimedRevocation, relocate_photo_to_held


class MemoryStorage:
    def __init__(self, objects: dict[str, bytes]) -> None:
        self.objects = dict(objects)
        self.copy_calls = 0
        self.delete_calls = 0

    def get_object_properties(self, *, bucket: str, object_name: str) -> StorageObjectProperties:
        del bucket
        try:
            value = self.objects[object_name]
        except KeyError as exc:
            raise FileNotFoundError(object_name) from exc
        return StorageObjectProperties(len(value), "image/jpeg", "etag")

    def fetch_object_bytes(self, *, bucket: str, object_name: str) -> bytes:
        del bucket
        try:
            return self.objects[object_name]
        except KeyError as exc:
            raise FileNotFoundError(object_name) from exc

    def copy_object(
        self,
        *,
        src_bucket: str,
        src_object: str,
        dst_bucket: str,
        dst_object: str,
        expected_size: int | None = None,
        expected_sha256: str | None = None,
    ) -> None:
        del src_bucket, dst_bucket
        self.copy_calls += 1
        source = self.objects[src_object]
        if expected_size is not None and len(source) != expected_size:
            raise StorageCopyVerificationError("bad source size")
        if expected_sha256 is not None and hashlib.sha256(source).hexdigest() != expected_sha256:
            raise StorageCopyVerificationError("bad source hash")
        existing = self.objects.get(dst_object)
        if existing is not None and existing != source:
            raise StorageCopyVerificationError("destination already differs")
        self.objects[dst_object] = source

    def delete_object(self, *, bucket: str, object_name: str) -> None:
        del bucket
        self.delete_calls += 1
        self.objects.pop(object_name, None)

    # Unused protocol methods.
    def generate_put_url(self, **_: object) -> tuple[str, datetime]:
        raise NotImplementedError

    def put_required_headers(self, *, content_type: str) -> dict[str, str]:
        raise NotImplementedError

    def put_object_bytes(self, **_: object) -> None:
        raise NotImplementedError

    def generate_get_url(self, **_: object) -> tuple[str, datetime]:
        raise NotImplementedError


def _claim(value: bytes) -> ClaimedRevocation:
    return ClaimedRevocation(
        photo_id="photo-1",
        review_id="review-1",
        bucket="photos",
        source_object_name="observations/photo-1.jpg",
        held_object_name="rejected/held/photo-1.jpg",
        expected_byte_count=len(value),
        expected_sha256=hashlib.sha256(value).hexdigest(),
        attempt_count=1,
    )


def test_relocation_verifies_destination_and_removes_clean_source() -> None:
    value = b"canonical-jpeg"
    claim = _claim(value)
    storage = MemoryStorage({claim.source_object_name: value})

    relocate_photo_to_held(storage, claim)

    assert claim.source_object_name not in storage.objects
    assert storage.objects[claim.held_object_name] == value
    assert storage.copy_calls == 1
    assert storage.delete_calls == 1


def test_relocation_recovers_when_source_is_already_gone() -> None:
    value = b"canonical-jpeg"
    claim = _claim(value)
    storage = MemoryStorage({claim.held_object_name: value})

    relocate_photo_to_held(storage, claim)

    assert storage.copy_calls == 0
    assert storage.delete_calls == 0


def test_relocation_fails_closed_when_existing_destination_hash_differs() -> None:
    value = b"canonical-jpeg"
    claim = _claim(value)
    storage = MemoryStorage(
        {
            claim.source_object_name: value,
            claim.held_object_name: b"tampered",
        }
    )

    with pytest.raises(StorageCopyVerificationError):
        relocate_photo_to_held(storage, claim)

    assert storage.objects[claim.source_object_name] == value
    assert storage.delete_calls == 0
