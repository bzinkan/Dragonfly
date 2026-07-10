from __future__ import annotations

import sys
from pathlib import Path

import httpx
import pytest

_SCRIPTS = Path(__file__).resolve().parents[2] / "scripts"
sys.path.insert(0, str(_SCRIPTS))

import smoke_azure_parent_kid as parent_smoke  # noqa: E402
import smoke_observation_w1 as observation_smoke  # noqa: E402


def test_observation_failure_never_logs_sas_or_response_body() -> None:
    response = httpx.Response(
        500,
        request=httpx.Request(
            "PUT", "https://example.blob.core.windows.net/photos/photo.jpg?sig=SECRET"
        ),
        headers={"x-ms-request-id": "azure-request-1"},
        json={"handoff_token": "SECRET", "detail": "private"},
    )

    with pytest.raises(RuntimeError) as raised:
        observation_smoke._expect(response, 200)

    message = str(raised.value)
    assert "?sig=" not in message
    assert "SECRET" not in message
    assert "azure-request-1" in message
    assert "/photos/photo.jpg" in message


def test_parent_failure_never_logs_handoff_token_or_body() -> None:
    with pytest.raises(RuntimeError) as raised:
        parent_smoke.expect(
            "/v1/groups/group/kids",
            500,
            {"handoff_token": "SECRET", "detail": {"code": "safe_code"}},
            headers={"x-request-id": "request-1"},
            expected_status=201,
        )

    message = str(raised.value)
    assert "SECRET" not in message
    assert "request-1" in message
    assert "safe_code" in message


def test_child_dto_rejects_raw_moderation_status() -> None:
    with pytest.raises(RuntimeError, match="moderation_status"):
        observation_smoke._assert_child_dto_minimized(
            {"id": "observation", "moderation_status": "pending"}
        )
