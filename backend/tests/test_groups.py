from collections.abc import AsyncIterator, Iterator
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession

import app.core.auth as auth_module
from app.api.routes.groups import _JOIN_CODE_ALPHABET, generate_join_code
from app.core.config import Settings
from app.db import models
from app.db.session import get_db_session
from app.main import create_app

_FIREBASE_UID = "firebase-parent-001"
_USER_ID = "01J0PARENTID0000000000ULID"


def _stub_token_verifier(monkeypatch: pytest.MonkeyPatch, uid: str = _FIREBASE_UID) -> None:
    """Replace the Firebase verifier with one that accepts any token for `uid`."""

    def fake_verify(token: str, settings: Settings) -> dict[str, object]:
        return {"uid": uid, "email": "parent@example.com"}

    monkeypatch.setattr(auth_module, "verify_firebase_id_token", fake_verify)


def _build_client_with_session(session_mock: AsyncMock) -> Iterator[TestClient]:
    """Create a TestClient whose DB session dependency returns `session_mock`."""
    app = create_app(Settings(env="local", app_version="test"))

    async def override() -> AsyncIterator[AsyncSession]:
        yield session_mock

    app.dependency_overrides[get_db_session] = override
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def fake_session() -> AsyncMock:
    return AsyncMock(spec=AsyncSession)


@pytest.fixture
def groups_client(fake_session: AsyncMock) -> Iterator[TestClient]:
    yield from _build_client_with_session(fake_session)


def _user_row(role: str = "parent") -> models.User:
    return models.User(
        id=_USER_ID,
        firebase_uid=_FIREBASE_UID,
        role=role,
        display_name="Brian",
    )


def _set_session_lookups(
    fake_session: AsyncMock,
    *,
    user: models.User | None,
    join_code_collision: bool = False,
) -> None:
    """Wire up `session.execute(...)` to return user lookup then join-code lookup."""
    user_result = MagicMock()
    user_result.scalar_one_or_none = MagicMock(return_value=user)

    code_result = MagicMock()
    # Return a sentinel id when the code is "taken" (collision branch). When
    # there's no collision the result is None and the route accepts the
    # candidate code.
    code_result.scalar_one_or_none = MagicMock(
        return_value=("collide" if join_code_collision else None)
    )

    fake_session.execute = AsyncMock(side_effect=[user_result, code_result])
    fake_session.add = MagicMock()
    fake_session.commit = AsyncMock()
    fake_session.refresh = AsyncMock()


# ---------------------------------------------------------------------------
# generate_join_code unit tests
# ---------------------------------------------------------------------------


def test_generate_join_code_is_six_chars_from_alphabet() -> None:
    code = generate_join_code()
    assert len(code) == 6
    assert all(ch in _JOIN_CODE_ALPHABET for ch in code)


def test_generate_join_code_excludes_ambiguous_chars() -> None:
    # Crockford base32 omits I, L, O, U so codes can be read aloud.
    forbidden = {"I", "L", "O", "U"}
    for _ in range(200):
        code = generate_join_code()
        assert not (set(code) & forbidden)


# ---------------------------------------------------------------------------
# POST /v1/groups
# ---------------------------------------------------------------------------


def test_create_group_requires_bearer_token(groups_client: TestClient) -> None:
    response = groups_client.post("/v1/groups", json={"name": "Family"})

    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"


def test_create_group_validates_name(
    groups_client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _stub_token_verifier(monkeypatch)

    response = groups_client.post(
        "/v1/groups",
        headers={"Authorization": "Bearer valid"},
        json={},
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"


def test_create_group_returns_404_when_user_row_missing(
    groups_client: TestClient,
    fake_session: AsyncMock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _stub_token_verifier(monkeypatch)

    user_result = MagicMock()
    user_result.scalar_one_or_none = MagicMock(return_value=None)
    fake_session.execute = AsyncMock(return_value=user_result)

    response = groups_client.post(
        "/v1/groups",
        headers={"Authorization": "Bearer valid"},
        json={"name": "Family"},
    )

    assert response.status_code == 404
    assert "parent-signup" in response.json()["error"]["message"]


def test_create_group_rejects_kid_role(
    groups_client: TestClient,
    fake_session: AsyncMock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _stub_token_verifier(monkeypatch)
    _set_session_lookups(fake_session, user=_user_row(role="kid"))

    response = groups_client.post(
        "/v1/groups",
        headers={"Authorization": "Bearer valid"},
        json={"name": "Sneaky Family"},
    )

    assert response.status_code == 403
    assert "'kid'" in response.json()["error"]["message"]
    fake_session.add.assert_not_called()


@pytest.mark.parametrize("role", ["parent", "teacher"])
def test_create_group_happy_path(
    groups_client: TestClient,
    fake_session: AsyncMock,
    monkeypatch: pytest.MonkeyPatch,
    role: str,
) -> None:
    _stub_token_verifier(monkeypatch)
    _set_session_lookups(fake_session, user=_user_row(role=role))

    response = groups_client.post(
        "/v1/groups",
        headers={"Authorization": "Bearer valid"},
        json={"name": f"{role.capitalize()} Group"},
    )

    assert response.status_code == 201
    body = response.json()
    assert body["name"] == f"{role.capitalize()} Group"
    assert body["owner_user_id"] == _USER_ID
    assert len(body["join_code"]) == 6
    assert all(ch in _JOIN_CODE_ALPHABET for ch in body["join_code"])
    assert isinstance(body["id"], str) and len(body["id"]) == 26  # ULID

    # Group + Membership added; both share the new group's id.
    assert fake_session.add.call_count == 2
    added_group: models.Group = fake_session.add.call_args_list[0].args[0]
    added_membership: models.Membership = fake_session.add.call_args_list[1].args[0]
    assert added_group.name == f"{role.capitalize()} Group"
    assert added_group.owner_user_id == _USER_ID
    assert added_group.join_code == body["join_code"]
    assert added_membership.group_id == added_group.id
    assert added_membership.user_id == _USER_ID
    assert added_membership.role == role
    fake_session.commit.assert_awaited_once()
    fake_session.refresh.assert_awaited_once_with(added_group)
