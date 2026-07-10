from __future__ import annotations

import time
from types import SimpleNamespace

import pytest
from cryptography.hazmat.primitives.asymmetric import rsa

import app.core.auth as auth_module
from app.core.config import Settings

_API_CLIENT_ID = "7dd9da3c-b7d6-45d4-955b-d7561c43f209"
_CLIENT_APP_ID = "60504e4c-6b5f-4031-a80a-3e4bdfae29b2"
_TENANT_ID = "18dbd7fa-c411-49bc-82fc-9ccaa26e3404"
_ISSUER = "https://login.microsoftonline.com/18dbd7fa-c411-49bc-82fc-9ccaa26e3404/v2.0"


def _token(
    *,
    private_key: rsa.RSAPrivateKey,
    audience: str,
    client_app_id: str = _CLIENT_APP_ID,
    scope: str | None = "user.access",
    tenant_id: str = _TENANT_ID,
    version: str = "2.0",
) -> str:
    now = int(time.time())
    claims = {
        "aud": audience,
        "exp": now + 3600,
        "iat": now,
        "iss": _ISSUER,
        "oid": "11111111-2222-3333-4444-555555555555",
        "azp": client_app_id,
        "sub": "test-parent-subject",
        "tid": tenant_id,
        "ver": version,
    }
    if scope is not None:
        claims["scp"] = scope
    return auth_module.jwt.encode(
        claims,
        private_key,
        algorithm="RS256",
        headers={"kid": "test-key"},
    )


def _patch_jwks(monkeypatch: pytest.MonkeyPatch, public_key: object) -> None:
    class FakeJwksClient:
        def __init__(self, _url: str) -> None:
            pass

        def get_signing_key_from_jwt(self, _token: str) -> SimpleNamespace:
            return SimpleNamespace(key=public_key)

    monkeypatch.setattr(auth_module.jwt, "PyJWKClient", FakeJwksClient)


def test_entra_v2_token_accepts_exact_api_client_id_audience(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    _patch_jwks(monkeypatch, private_key.public_key())
    settings = Settings(entra_api_audience=_API_CLIENT_ID, entra_issuer=_ISSUER)

    claims = auth_module._verify_entra_inline(
        _token(private_key=private_key, audience=_API_CLIENT_ID),
        settings,
    )

    assert claims["aud"] == _API_CLIENT_ID


@pytest.mark.parametrize(
    "wrong_audience",
    ["api://hinterland-api", "00000000-0000-0000-0000-000000000000"],
)
def test_entra_v2_token_rejects_scope_uri_and_other_audiences(
    monkeypatch: pytest.MonkeyPatch,
    wrong_audience: str,
) -> None:
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    _patch_jwks(monkeypatch, private_key.public_key())
    settings = Settings(entra_api_audience=_API_CLIENT_ID, entra_issuer=_ISSUER)

    with pytest.raises(auth_module.InvalidAuthToken):
        auth_module._verify_entra_inline(
            _token(private_key=private_key, audience=wrong_audience),
            settings,
        )


@pytest.mark.parametrize(
    "token_overrides",
    [
        {"scope": None},
        {"scope": "openid profile"},
        {"client_app_id": "00000000-0000-0000-0000-000000000000"},
        {"tenant_id": "00000000-0000-0000-0000-000000000000"},
        {"version": "1.0"},
    ],
)
def test_entra_v2_token_rejects_wrong_scope_client_tenant_or_version(
    monkeypatch: pytest.MonkeyPatch,
    token_overrides: dict[str, str | None],
) -> None:
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    _patch_jwks(monkeypatch, private_key.public_key())
    settings = Settings(entra_api_audience=_API_CLIENT_ID, entra_issuer=_ISSUER)

    with pytest.raises(auth_module.InvalidAuthToken):
        auth_module._verify_entra_inline(
            _token(
                private_key=private_key,
                audience=_API_CLIENT_ID,
                **token_overrides,
            ),
            settings,
        )
