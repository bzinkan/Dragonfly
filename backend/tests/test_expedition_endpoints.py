"""Tests for /v1/expeditions/* endpoints."""

from __future__ import annotations

from collections.abc import AsyncIterator, Iterator
from datetime import UTC, datetime
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.db import models
from app.db.session import get_db_session
from app.main import create_app
from tests.helpers.auth import stub_token_verifier

_FIREBASE_UID = "firebase-kid-001"
_USER_ID = "01J0KIDID0000000000000ULID"
_GROUP_ID = "01J0GROUPID00000000000ULID"


def _stub_token_verifier(monkeypatch: pytest.MonkeyPatch) -> None:
    """Back-compat shim that delegates to the shared helper."""
    stub_token_verifier(monkeypatch, uid=_FIREBASE_UID, role="kid", group_id=_GROUP_ID)


def _build_client(fake_session: AsyncMock) -> Iterator[TestClient]:
    app = create_app(Settings(env="local", app_version="test"))

    async def override() -> AsyncIterator[AsyncSession]:
        yield fake_session

    app.dependency_overrides[get_db_session] = override
    with TestClient(app, raise_server_exceptions=True) as test_client:
        yield test_client


@pytest.fixture
def fake_session() -> AsyncMock:
    return AsyncMock(spec=AsyncSession)


def _user() -> models.User:
    return models.User(id=_USER_ID, firebase_uid=_FIREBASE_UID, role="kid", display_name="Kid")


def _exp_body(
    *,
    exp_id: str,
    prerequisites: list[dict[str, object]] | None = None,
    steps_count: int = 1,
) -> dict[str, Any]:
    return {
        "id": exp_id,
        "title": f"Test {exp_id}",
        "tier": 1,
        "duration_minutes": 20,
        "environments": ["yard"],
        "intro": "Find some things.",
        "outro": "Real science.",
        "prerequisites": prerequisites or [],
        "steps": [
            {"id": f"s{i}", "description": "x", "match": {"kind": "any_organism"}}
            for i in range(steps_count)
        ],
    }


def _content(exp_id: str, body: dict[str, Any]) -> models.ExpeditionContent:
    return models.ExpeditionContent(
        id=exp_id, tier=body["tier"], content_hash="x", body=body, archived=False
    )


# ---------------------------------------------------------------------------
# GET /v1/expeditions/available
# ---------------------------------------------------------------------------


def _wire_available(
    fake_session: AsyncMock,
    *,
    user: models.User | None,
    dex_count: int = 0,
    completed_ids: list[str] | None = None,
    any_progress_ids: list[str] | None = None,
    contents: list[models.ExpeditionContent] | None = None,
) -> None:
    user_result = MagicMock()
    user_result.scalar_one_or_none = MagicMock(return_value=user)

    dex_result = MagicMock()
    dex_result.all = MagicMock(return_value=[(dex_count,)])

    completed_result = MagicMock()
    completed_result.all = MagicMock(return_value=[(i,) for i in (completed_ids or [])])

    any_progress_result = MagicMock()
    any_progress_result.all = MagicMock(return_value=[(i,) for i in (any_progress_ids or [])])

    content_result = MagicMock()
    scalars = MagicMock()
    scalars.all = MagicMock(return_value=contents or [])
    content_result.scalars = MagicMock(return_value=scalars)

    side_effects: list[Any] = [user_result]
    if user is not None:
        side_effects.extend([dex_result, completed_result, any_progress_result, content_result])

    fake_session.execute = AsyncMock(side_effect=side_effects)


def test_available_requires_bearer(fake_session: AsyncMock) -> None:
    for client in _build_client(fake_session):
        response = client.get("/v1/expeditions/available")
        assert response.status_code == 401


def test_available_403_when_no_postgres_user(
    monkeypatch: pytest.MonkeyPatch, fake_session: AsyncMock
) -> None:
    _stub_token_verifier(monkeypatch)
    _wire_available(fake_session, user=None)
    for client in _build_client(fake_session):
        response = client.get("/v1/expeditions/available", headers={"Authorization": "Bearer fake"})
        assert response.status_code == 403


def test_available_returns_unstarted_unblocked_expeditions(
    monkeypatch: pytest.MonkeyPatch, fake_session: AsyncMock
) -> None:
    _stub_token_verifier(monkeypatch)
    contents = [
        _content("a", _exp_body(exp_id="a")),
        _content("b", _exp_body(exp_id="b")),
    ]
    _wire_available(
        fake_session,
        user=_user(),
        dex_count=0,
        completed_ids=[],
        any_progress_ids=[],
        contents=contents,
    )
    for client in _build_client(fake_session):
        response = client.get("/v1/expeditions/available", headers={"Authorization": "Bearer fake"})
        assert response.status_code == 200
        body = response.json()
        assert [item["id"] for item in body["items"]] == ["a", "b"]


def test_available_filters_already_started(
    monkeypatch: pytest.MonkeyPatch, fake_session: AsyncMock
) -> None:
    _stub_token_verifier(monkeypatch)
    contents = [
        _content("a", _exp_body(exp_id="a")),
        _content("b", _exp_body(exp_id="b")),
    ]
    _wire_available(
        fake_session,
        user=_user(),
        any_progress_ids=["a"],  # started, so not available
        contents=contents,
    )
    for client in _build_client(fake_session):
        response = client.get("/v1/expeditions/available", headers={"Authorization": "Bearer fake"})
        assert [i["id"] for i in response.json()["items"]] == ["b"]


def test_available_filters_unmet_dex_count_prereq(
    monkeypatch: pytest.MonkeyPatch, fake_session: AsyncMock
) -> None:
    _stub_token_verifier(monkeypatch)
    contents = [
        _content(
            "needs_5",
            _exp_body(
                exp_id="needs_5",
                prerequisites=[{"kind": "dex_count_at_least", "value": 5}],
            ),
        )
    ]
    _wire_available(fake_session, user=_user(), dex_count=2, contents=contents)
    for client in _build_client(fake_session):
        response = client.get("/v1/expeditions/available", headers={"Authorization": "Bearer fake"})
        assert response.json()["items"] == []


def test_available_filters_unmet_completed_prereq(
    monkeypatch: pytest.MonkeyPatch, fake_session: AsyncMock
) -> None:
    _stub_token_verifier(monkeypatch)
    contents = [
        _content(
            "sequel",
            _exp_body(
                exp_id="sequel",
                prerequisites=[{"kind": "completed_expedition", "value": "backyard_starter"}],
            ),
        )
    ]
    _wire_available(fake_session, user=_user(), completed_ids=[], contents=contents)
    for client in _build_client(fake_session):
        response = client.get("/v1/expeditions/available", headers={"Authorization": "Bearer fake"})
        assert response.json()["items"] == []


# ---------------------------------------------------------------------------
# POST /v1/expeditions/{id}/start
# ---------------------------------------------------------------------------


def _wire_start(
    fake_session: AsyncMock,
    *,
    user: models.User | None,
    content: models.ExpeditionContent | None,
    dex_count: int = 0,
    completed_ids: list[str] | None = None,
    existing_progress_id: str | None = None,
) -> None:
    user_result = MagicMock()
    user_result.scalar_one_or_none = MagicMock(return_value=user)

    content_result = MagicMock()
    content_result.scalar_one_or_none = MagicMock(return_value=content)

    dex_result = MagicMock()
    dex_result.all = MagicMock(return_value=[(dex_count,)])

    completed_result = MagicMock()
    completed_result.all = MagicMock(return_value=[(i,) for i in (completed_ids or [])])

    existing_result = MagicMock()
    existing_result.scalar_one_or_none = MagicMock(return_value=existing_progress_id)

    side_effects: list[Any] = [user_result]
    if user is not None:
        side_effects.append(content_result)
        if content is not None:
            side_effects.extend([dex_result, completed_result, existing_result])

    fake_session.execute = AsyncMock(side_effect=side_effects)
    fake_session.add = MagicMock()
    fake_session.commit = AsyncMock()
    fake_session.refresh = AsyncMock(
        side_effect=lambda obj: setattr(
            obj, "created_at", datetime(2026, 5, 10, 12, 0, 0, tzinfo=UTC)
        )
    )


def test_start_requires_bearer(fake_session: AsyncMock) -> None:
    for client in _build_client(fake_session):
        response = client.post("/v1/expeditions/x/start")
        assert response.status_code == 401


def test_start_404_when_expedition_missing(
    monkeypatch: pytest.MonkeyPatch, fake_session: AsyncMock
) -> None:
    _stub_token_verifier(monkeypatch)
    _wire_start(fake_session, user=_user(), content=None)
    for client in _build_client(fake_session):
        response = client.post(
            "/v1/expeditions/missing/start",
            headers={"Authorization": "Bearer fake"},
        )
        assert response.status_code == 404


def test_start_409_when_prereq_unmet(
    monkeypatch: pytest.MonkeyPatch, fake_session: AsyncMock
) -> None:
    _stub_token_verifier(monkeypatch)
    body = _exp_body(exp_id="x", prerequisites=[{"kind": "dex_count_at_least", "value": 5}])
    _wire_start(fake_session, user=_user(), content=_content("x", body), dex_count=0)
    for client in _build_client(fake_session):
        response = client.post("/v1/expeditions/x/start", headers={"Authorization": "Bearer fake"})
        assert response.status_code == 409
        assert "Prerequisites" in response.json()["error"]["message"]


def test_start_409_when_already_started(
    monkeypatch: pytest.MonkeyPatch, fake_session: AsyncMock
) -> None:
    _stub_token_verifier(monkeypatch)
    body = _exp_body(exp_id="x")
    _wire_start(
        fake_session,
        user=_user(),
        content=_content("x", body),
        existing_progress_id="some-id",
    )
    for client in _build_client(fake_session):
        response = client.post("/v1/expeditions/x/start", headers={"Authorization": "Bearer fake"})
        assert response.status_code == 409
        assert "already started" in response.json()["error"]["message"]


def test_start_happy_path_creates_progress_row(
    monkeypatch: pytest.MonkeyPatch, fake_session: AsyncMock
) -> None:
    _stub_token_verifier(monkeypatch)
    body = _exp_body(exp_id="backyard_starter")
    _wire_start(fake_session, user=_user(), content=_content("backyard_starter", body))
    for client in _build_client(fake_session):
        response = client.post(
            "/v1/expeditions/backyard_starter/start",
            headers={"Authorization": "Bearer fake"},
        )
        assert response.status_code == 201
        body_json = response.json()
        assert body_json["expedition_id"] == "backyard_starter"

    fake_session.add.assert_called_once()
    progress: models.ExpeditionProgress = fake_session.add.call_args.args[0]
    assert isinstance(progress, models.ExpeditionProgress)
    assert progress.user_id == _USER_ID
    assert progress.group_id == _GROUP_ID
    assert progress.expedition_id == "backyard_starter"
    assert progress.completed_steps == {}
