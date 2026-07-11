from __future__ import annotations

import importlib.util
import json
import sys
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

import pytest

_ROOT = Path(__file__).resolve().parents[2]
_SCRIPT = _ROOT / "scripts/verify_parent_callback.py"
_SPEC = importlib.util.spec_from_file_location("verify_parent_callback", _SCRIPT)
assert _SPEC is not None and _SPEC.loader is not None
verifier = importlib.util.module_from_spec(_SPEC)
sys.modules[_SPEC.name] = verifier
_SPEC.loader.exec_module(verifier)

SHA = "a" * 40
PROBE = "safe_route_probe_123456"
CALLBACK_HTML = b"<!doctype html><title>Finishing secure sign-in</title>"
CALLBACK_HEADERS = {
    "Content-Type": "text/html; charset=utf-8",
    "Cache-Control": "no-store",
    "Referrer-Policy": "no-referrer",
    "X-Content-Type-Options": "nosniff",
}
ORIGINS = (
    verifier.Origin("custom", "https://parents.example.test"),
    verifier.Origin("azure", "https://parents-resource.example.test"),
)


@dataclass
class FakeResponse:
    body: bytes
    status: int = 200
    headers: dict[str, str] = field(default_factory=dict)
    final_url: str | None = None

    def read(self) -> bytes:
        return self.body

    def geturl(self) -> str:
        assert self.final_url is not None
        return self.final_url

    def getcode(self) -> int:
        return self.status

    def close(self) -> None:
        return None

    def __enter__(self) -> FakeResponse:
        return self

    def __exit__(self, exc_type: object, exc: object, traceback: object) -> Literal[False]:
        return False


class FakeOpener:
    def __init__(self, responses: dict[tuple[str, str], FakeResponse]) -> None:
        self.responses = responses
        self.requests: list[urllib.request.Request] = []

    def open(self, request: urllib.request.Request, timeout: float) -> FakeResponse:
        assert timeout > 0
        self.requests.append(request)
        parsed = urllib.parse.urlsplit(request.full_url)
        template = self.responses[(parsed.netloc, parsed.path)]
        return FakeResponse(
            body=template.body,
            status=template.status,
            headers=template.headers.copy(),
            final_url=template.final_url or request.full_url,
        )


def _responses(
    *,
    first_html: bytes = CALLBACK_HTML,
    second_html: bytes = CALLBACK_HTML,
    first_marker: bytes | None = None,
    callback_status: int = 200,
    callback_headers: dict[str, str] | None = None,
    callback_final_url: str | None = None,
) -> dict[tuple[str, str], FakeResponse]:
    responses: dict[tuple[str, str], FakeResponse] = {}
    for index, origin in enumerate(ORIGINS):
        host = urllib.parse.urlsplit(origin.base_url).netloc
        responses[(host, verifier.BUILD_PATH)] = FakeResponse(
            body=(
                first_marker
                if index == 0 and first_marker is not None
                else json.dumps({"surface": "parents", "commit_sha": SHA}).encode()
            ),
        )
        responses[(host, verifier.CALLBACK_PATH)] = FakeResponse(
            body=first_html if index == 0 else second_html,
            status=callback_status if index == 0 else 200,
            headers=(callback_headers or CALLBACK_HEADERS).copy()
            if index == 0
            else CALLBACK_HEADERS.copy(),
            final_url=callback_final_url if index == 0 else None,
        )
    return responses


def _verify(opener: FakeOpener, **kwargs: Any) -> dict[str, object]:
    return verifier.verify_parent_callback(
        expected_sha=SHA,
        origins=ORIGINS,
        opener=opener,
        probe=PROBE,
        **kwargs,
    )


def test_success_uses_safe_requests_and_writes_sanitized_evidence(tmp_path: Path) -> None:
    opener = FakeOpener(_responses())
    evidence_path = tmp_path / "callback-evidence.json"
    expected_html = tmp_path / "callback.html"
    expected_html.write_bytes(CALLBACK_HTML)

    evidence = _verify(
        opener,
        expected_html=expected_html,
        evidence_path=evidence_path,
    )

    assert evidence["result"] == "passed"
    assert evidence["target_count"] == 2
    assert evidence["cross_target_artifact_match"] is True
    assert evidence["local_artifact_match"] is True
    assert evidence["oauth_material_recorded"] is False
    assert evidence["transport"] == {
        "authentication_sent": False,
        "cookies_sent": False,
        "javascript_used": False,
        "redirects_followed": False,
    }

    assert len(opener.requests) == 4
    for request in opener.requests:
        parsed = urllib.parse.urlsplit(request.full_url)
        assert request.get_method() == "GET"
        assert request.data is None
        assert parsed.scheme == "https"
        assert parsed.path in {verifier.BUILD_PATH, verifier.CALLBACK_PATH}
        assert urllib.parse.parse_qs(parsed.query) == {"route_probe": [PROBE]}
        assert dict(request.header_items()) == {"User-agent": verifier.USER_AGENT}
        assert request.get_header("Authorization") is None
        assert request.get_header("Cookie") is None

    stored = json.loads(evidence_path.read_text(encoding="utf-8"))
    serialized = json.dumps(stored, sort_keys=True)
    assert stored == evidence
    assert PROBE not in serialized
    assert "https://" not in serialized
    assert "example.test" not in serialized
    assert "Finishing secure sign-in" not in serialized
    assert "Cache-Control" not in serialized
    assert "no-referrer" not in serialized
    assert "nosniff" not in serialized


def test_callback_404_fails_closed() -> None:
    with pytest.raises(
        verifier.VerificationError, match=r"custom /auth/callback returned HTTP 404"
    ):
        _verify(FakeOpener(_responses(callback_status=404)))


@pytest.mark.parametrize(
    ("status", "final_url", "match"),
    [
        (302, None, r"returned HTTP 302"),
        (200, "https://other.example.test/callback", r"redirected"),
    ],
)
def test_redirects_fail_closed(status: int, final_url: str | None, match: str) -> None:
    with pytest.raises(verifier.VerificationError, match=match):
        _verify(FakeOpener(_responses(callback_status=status, callback_final_url=final_url)))


def test_wrong_content_type_fails_closed() -> None:
    headers = CALLBACK_HEADERS | {"Content-Type": "application/json"}
    with pytest.raises(verifier.VerificationError, match=r"was not text/html"):
        _verify(FakeOpener(_responses(callback_headers=headers)))


def test_missing_sentinel_fails_closed() -> None:
    with pytest.raises(verifier.VerificationError, match=r"lacked the callback sentinel"):
        _verify(FakeOpener(_responses(first_html=b"<!doctype html><title>Not found</title>")))


def test_stale_build_marker_fails_closed() -> None:
    with pytest.raises(verifier.VerificationError, match=r"served a stale build marker"):
        _verify(
            FakeOpener(
                _responses(
                    first_marker=json.dumps({"surface": "parents", "commit_sha": "b" * 40}).encode()
                )
            )
        )


def test_different_callback_artifacts_fail_closed() -> None:
    different = CALLBACK_HTML + b"<!-- different -->"
    with pytest.raises(verifier.VerificationError, match=r"artifacts differ"):
        _verify(FakeOpener(_responses(second_html=different)))


@pytest.mark.parametrize(
    ("header", "value", "match"),
    [
        ("Cache-Control", "public, max-age=60", r"did not disable storage"),
        ("Referrer-Policy", "origin", r"did not disable referrers"),
        ("X-Content-Type-Options", "", r"did not disable MIME sniffing"),
    ],
)
def test_missing_security_policy_fails_closed(header: str, value: str, match: str) -> None:
    headers = CALLBACK_HEADERS | {header: value}
    with pytest.raises(verifier.VerificationError, match=match):
        _verify(FakeOpener(_responses(callback_headers=headers)))


def test_expected_local_artifact_must_match(tmp_path: Path) -> None:
    expected_html = tmp_path / "callback.html"
    expected_html.write_bytes(CALLBACK_HTML + b"<!-- local mismatch -->")
    with pytest.raises(verifier.VerificationError, match=r"differs from the expected"):
        _verify(FakeOpener(_responses()), expected_html=expected_html)


def test_origin_parser_rejects_paths_credentials_and_non_https() -> None:
    for raw in (
        "parents=http://parents.example.test",
        "parents=https://user:secret@parents.example.test",
        "parents=https://parents.example.test/path",
        "bad label=https://parents.example.test",
    ):
        with pytest.raises(Exception, match=r"origin must"):
            verifier._parse_origin(raw)
