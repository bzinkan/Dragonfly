from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from app.core.auth import clear_user_claims_cache
from app.core.config import Settings
from app.main import create_app


@pytest.fixture(autouse=True)
def _reset_claim_cache() -> Iterator[None]:
    """Drop the Option-C 30-second user-claims TTL cache between tests.

    Tests that go through the resolved auth path (not the stub short-circuit)
    cache the (oid, ulid -> role/group_id) lookup; without this fixture,
    state leaks between tests and assertions on role/group_id wobble.
    """
    yield
    clear_user_claims_cache()


@pytest.fixture
def client() -> Iterator[TestClient]:
    app = create_app(Settings(env="local", app_version="test"))
    with TestClient(app) as test_client:
        yield test_client
