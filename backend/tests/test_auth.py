from fastapi.testclient import TestClient

import app.core.auth as auth_module
from app.core.config import Settings


def test_me_requires_bearer_token(client: TestClient) -> None:
    response = client.get("/v1/me")

    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"
    assert response.json()["error"]["message"] == "Missing bearer token"


def test_me_returns_current_firebase_user(
    client: TestClient,
    monkeypatch,
) -> None:
    def fake_verify_id_token(token: str, settings: Settings) -> dict[str, object]:
        assert token == "valid-token"
        assert settings.env == "local"
        return {
            "uid": "firebase-user-1",
            "email": "parent@example.com",
            "role": "parent",
            "group_id": "group-1",
            "parent_id": "parent-1",
        }

    monkeypatch.setattr(auth_module, "verify_firebase_id_token", fake_verify_id_token)

    response = client.get("/v1/me", headers={"Authorization": "Bearer valid-token"})

    assert response.status_code == 200
    assert response.json() == {
        "uid": "firebase-user-1",
        "email": "parent@example.com",
        "role": "parent",
        "group_id": "group-1",
        "kid_id": None,
        "parent_id": "parent-1",
        "teacher_id": None,
    }


def test_me_rejects_invalid_firebase_token(
    client: TestClient,
    monkeypatch,
) -> None:
    def fake_verify_id_token(token: str, settings: Settings) -> dict[str, object]:
        raise auth_module.InvalidAuthToken("Invalid bearer token")

    monkeypatch.setattr(auth_module, "verify_firebase_id_token", fake_verify_id_token)

    response = client.get("/v1/me", headers={"Authorization": "Bearer bad-token"})

    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"
    assert response.json()["error"]["message"] == "Invalid bearer token"
