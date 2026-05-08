#!/usr/bin/env python3
"""End-to-end smoke test for Phase 4 (parent signup -> groups -> kids -> /v1/me).

Flow:
    1. Firebase signUp creates a parent (Firebase Auth REST, public Web API key).
    2. POST /v1/auth/parent-signup materializes the `users` row, sets the
       Firebase custom claim role=parent.
    3. Force-refresh the parent's ID token so the new claim takes effect.
    4. POST /v1/groups creates the family group, returns a 6-char join code.
    5. POST /v1/groups/{group_id}/kids admin-creates a kid via Firebase Admin
       SDK on the server side, returns a Firebase custom token.
    6. signInWithCustomToken (kid) exchanges the custom token for an ID token.
    7. GET /v1/me as the kid asserts the kid's identity context.

Usage:
    python scripts/smoke_phase4.py

Configuration (env vars; sensible defaults baked in for dev):
    DRAGONFLY_API_BASE_URL       default: https://api.dragonfly-app.net
    DRAGONFLY_FIREBASE_API_KEY   default: dev project's Web API key (public)
    DRAGONFLY_SMOKE_EMAIL        default: smoke+<timestamp>@dragonfly-test.invalid
    DRAGONFLY_SMOKE_PASSWORD     default: a fixed dev-only password

Standard library only (no third-party deps). Exits 0 on success, non-zero
on any failure with a clear message indicating which step failed.

Test users left behind: every run creates a Firebase user (parent + kid)
plus the corresponding `users`/`memberships`/`groups` rows. They accumulate.
Clean them up periodically via Firebase Console or a separate teardown
script. Don't run this against prod -- it's named `*-test.invalid` to
make any leakage obvious.
"""

from __future__ import annotations

import json
import os
import sys
import time
import urllib.error
import urllib.request
from typing import Any

API_BASE = os.environ.get(
    "DRAGONFLY_API_BASE_URL", "https://api.dragonfly-app.net"
).rstrip("/")
FIREBASE_API_KEY = os.environ.get(
    "DRAGONFLY_FIREBASE_API_KEY",
    "AIzaSyAg2gIzrXoYbeLx5cKWB1QXCZiDWEF2Yh4",
)
SMOKE_EMAIL = os.environ.get(
    "DRAGONFLY_SMOKE_EMAIL",
    f"smoke+{int(time.time())}@dragonfly-test.invalid",
)
SMOKE_PASSWORD = os.environ.get(
    "DRAGONFLY_SMOKE_PASSWORD",
    "dragonfly-smoke-test-2026!",
)


def request(
    method: str,
    url: str,
    *,
    headers: dict[str, str] | None = None,
    body: dict[str, Any] | None = None,
) -> tuple[int, Any]:
    """Issue an HTTP request and return (status, parsed-body).

    Body is JSON-encoded if provided. Error responses are also JSON-decoded
    when possible; otherwise the raw text is returned. Network errors raise.
    """
    encoded = json.dumps(body).encode() if body is not None else None
    req_headers = dict(headers or {})
    if body is not None:
        req_headers.setdefault("Content-Type", "application/json")
    req = urllib.request.Request(url, data=encoded, method=method, headers=req_headers)
    try:
        with urllib.request.urlopen(req) as resp:  # noqa: S310 -- internal smoke
            return resp.status, json.loads(resp.read() or b"{}")
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        try:
            payload: Any = json.loads(raw)
        except json.JSONDecodeError:
            payload = raw
        return exc.code, payload


def expect(
    label: str,
    status: int,
    payload: Any,
    *,
    expected_status: int | tuple[int, ...] = 200,
) -> None:
    """Assert a response matches the expected status; pretty-print on failure."""
    expected = (
        expected_status if isinstance(expected_status, tuple) else (expected_status,)
    )
    if status in expected:
        return
    print(f"\n[FAIL] {label}: got HTTP {status}, expected {expected}")
    print(f"  body: {json.dumps(payload, indent=2)[:600]}")
    sys.exit(2)


def main() -> int:
    print(f"API base:         {API_BASE}")
    print(f"Firebase API key: {FIREBASE_API_KEY[:8]}... (public, embedded in clients)")
    print(f"Test parent:      {SMOKE_EMAIL}")
    print()

    # --------------------------------------------------------------------- #
    # 1. Firebase signUp creates the parent.
    # --------------------------------------------------------------------- #
    print("[1/7] Firebase signUp (parent)...")
    status, payload = request(
        "POST",
        f"https://identitytoolkit.googleapis.com/v1/accounts:signUp?key={FIREBASE_API_KEY}",
        body={
            "email": SMOKE_EMAIL,
            "password": SMOKE_PASSWORD,
            "returnSecureToken": True,
        },
    )
    expect("Firebase signUp", status, payload)
    parent_id_token = payload["idToken"]
    parent_refresh_token = payload["refreshToken"]
    parent_firebase_uid = payload["localId"]
    print(f"      Firebase uid: {parent_firebase_uid}")

    # --------------------------------------------------------------------- #
    # 2. POST /v1/auth/parent-signup -- materializes the `users` row, sets
    #    the Firebase custom claim role=parent.
    # --------------------------------------------------------------------- #
    print("[2/7] POST /v1/auth/parent-signup...")
    status, payload = request(
        "POST",
        f"{API_BASE}/v1/auth/parent-signup",
        headers={"Authorization": f"Bearer {parent_id_token}"},
        body={"display_name": "Smoke Test Parent"},
    )
    expect("/v1/auth/parent-signup", status, payload)
    parent_user_id = payload["id"]
    assert payload["role"] == "parent", payload
    assert payload["firebase_uid"] == parent_firebase_uid, payload
    print(f"      users row: id={parent_user_id} role=parent")

    # --------------------------------------------------------------------- #
    # 3. Force-refresh the ID token so the new role=parent claim takes
    #    effect on the next API call.
    # --------------------------------------------------------------------- #
    print("[3/7] Refresh parent ID token (pick up role=parent claim)...")
    status, payload = request(
        "POST",
        f"https://securetoken.googleapis.com/v1/token?key={FIREBASE_API_KEY}",
        body={
            "grant_type": "refresh_token",
            "refresh_token": parent_refresh_token,
        },
    )
    expect("Firebase refresh", status, payload)
    parent_id_token = payload["id_token"]
    print("      refreshed")

    # --------------------------------------------------------------------- #
    # 4. POST /v1/groups -- creates the family group + parent's membership.
    # --------------------------------------------------------------------- #
    print("[4/7] POST /v1/groups...")
    status, payload = request(
        "POST",
        f"{API_BASE}/v1/groups",
        headers={"Authorization": f"Bearer {parent_id_token}"},
        body={"name": "Smoke Test Family"},
    )
    expect("/v1/groups", status, payload, expected_status=201)
    group_id = payload["id"]
    join_code = payload["join_code"]
    assert payload["owner_user_id"] == parent_user_id, payload
    assert len(join_code) == 6, payload
    print(f"      group: id={group_id} join_code={join_code}")

    # --------------------------------------------------------------------- #
    # 5. POST /v1/groups/{group_id}/kids -- admin-create a kid via Firebase
    #    Admin SDK + return a custom token for the kid's first sign-in.
    # --------------------------------------------------------------------- #
    print("[5/7] POST /v1/groups/{group_id}/kids...")
    status, payload = request(
        "POST",
        f"{API_BASE}/v1/groups/{group_id}/kids",
        headers={"Authorization": f"Bearer {parent_id_token}"},
        body={"display_name": "Sparrow", "age_band": "9-10"},
    )
    expect("/v1/groups/{group_id}/kids", status, payload, expected_status=201)
    kid_user_id = payload["id"]
    kid_firebase_uid = payload["firebase_uid"]
    kid_custom_token = payload["custom_token"]
    assert payload["display_name"] == "Sparrow", payload
    assert payload["age_band"] == "9-10", payload
    print(f"      kid: id={kid_user_id} firebase_uid={kid_firebase_uid}")

    # --------------------------------------------------------------------- #
    # 6. Exchange the kid's custom token for an ID token via Firebase REST.
    # --------------------------------------------------------------------- #
    print("[6/7] signInWithCustomToken (kid)...")
    status, payload = request(
        "POST",
        f"https://identitytoolkit.googleapis.com/v1/accounts:signInWithCustomToken?key={FIREBASE_API_KEY}",
        body={"token": kid_custom_token, "returnSecureToken": True},
    )
    expect("Firebase signInWithCustomToken", status, payload)
    kid_id_token = payload["idToken"]
    print("      kid signed in")

    # --------------------------------------------------------------------- #
    # 7. GET /v1/me as the kid -- the round-trip exit-criterion.
    # --------------------------------------------------------------------- #
    print("[7/7] GET /v1/me (kid)...")
    status, payload = request(
        "GET",
        f"{API_BASE}/v1/me",
        headers={"Authorization": f"Bearer {kid_id_token}"},
    )
    expect("/v1/me", status, payload)
    assert payload["uid"] == kid_firebase_uid, payload
    assert payload["role"] == "kid", payload
    assert payload["group_id"] == group_id, payload
    assert payload["parent_id"] == parent_user_id, payload
    print(
        f"      me: uid={payload['uid']} role={payload['role']} "
        f"group_id={payload['group_id']}"
    )

    print("\nALL CHECKS PASSED -- Phase 4 round-trip works end-to-end.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
