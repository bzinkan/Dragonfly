"""Tests for POST /v1/auth/consent (public unauthenticated)."""

from __future__ import annotations

from collections.abc import AsyncIterator, Iterator
from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.db.session import get_db_session
from app.main import create_app


@pytest.fixture
def fake_session() -> AsyncMock:
    return AsyncMock(spec=AsyncSession)


@pytest.fixture
def consent_client(fake_session: AsyncMock) -> Iterator[TestClient]:
    app = create_app(Settings(env="local", app_version="test"))

    async def override() -> AsyncIterator[AsyncSession]:
        yield fake_session

    app.dependency_overrides[get_db_session] = override
    with TestClient(app, raise_server_exceptions=True) as test_client:
        yield test_client


def test_consent_records_with_no_auth(consent_client: TestClient) -> None:
    """Public endpoint -- no Authorization header required."""
    response = consent_client.post(
        "/v1/auth/consent",
        json={"email": "parent@example.com"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["recorded_at"]
    assert body["policy_version"]


def test_consent_accepts_explicit_policy_version(consent_client: TestClient) -> None:
    response = consent_client.post(
        "/v1/auth/consent",
        json={"email": "parent@example.com", "policy_version": "2027-01-01"},
    )
    assert response.status_code == 200
    assert response.json()["policy_version"] == "2027-01-01"


def test_consent_422_on_missing_email(consent_client: TestClient) -> None:
    response = consent_client.post("/v1/auth/consent", json={})
    assert response.status_code == 422


def test_consent_422_on_malformed_email(consent_client: TestClient) -> None:
    response = consent_client.post("/v1/auth/consent", json={"email": "not-an-email"})
    assert response.status_code == 422
