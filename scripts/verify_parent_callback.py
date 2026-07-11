#!/usr/bin/env python3
"""Verify the deployed parent-auth callback without sending OAuth material.

This probe is intentionally a plain HTTP client. It does not execute JavaScript,
send cookies or authorization headers, or follow redirects. The callback request
contains only a random ``route_probe`` value so it can prove that Static Web Apps
serves the exported callback document directly.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import secrets
import sys
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol, cast

CALLBACK_PATH = "/auth/callback"
BUILD_PATH = "/.well-known/hinterland-build.json"
CALLBACK_SENTINEL = "Finishing secure sign-in"
USER_AGENT = "Hinterland-W1-Parent-Callback-Verifier/1.0"

_LABEL_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,63}\Z")
_SHA_RE = re.compile(r"[0-9a-f]{40}\Z")
_PROBE_RE = re.compile(r"[A-Za-z0-9_-]{16,64}\Z")


class VerificationError(RuntimeError):
    """A callback deployment failed its fail-closed verification contract."""


class Response(Protocol):
    status: int
    headers: Any

    def read(self) -> bytes: ...

    def geturl(self) -> str: ...

    def getcode(self) -> int: ...

    def close(self) -> None: ...

    def __enter__(self) -> Response: ...

    def __exit__(self, exc_type: object, exc: object, traceback: object) -> object: ...


class Opener(Protocol):
    def open(self, request: urllib.request.Request, timeout: float) -> Response: ...


@dataclass(frozen=True)
class Origin:
    label: str
    base_url: str


class _NoRedirectHandler(urllib.request.HTTPRedirectHandler):
    def redirect_request(
        self,
        req: urllib.request.Request,
        fp: Any,
        code: int,
        msg: str,
        headers: Any,
        newurl: str,
    ) -> None:
        return None


def _parse_origin(value: str) -> Origin:
    label, separator, raw_url = value.partition("=")
    if not separator or not _LABEL_RE.fullmatch(label):
        raise argparse.ArgumentTypeError("origin must be a safe LABEL=https://host value")

    parsed = urllib.parse.urlsplit(raw_url)
    if (
        parsed.scheme != "https"
        or not parsed.netloc
        or parsed.username is not None
        or parsed.password is not None
        or parsed.path not in ("", "/")
        or parsed.query
        or parsed.fragment
    ):
        raise argparse.ArgumentTypeError(
            "origin must be an HTTPS origin without path or credentials"
        )

    return Origin(label=label, base_url=f"https://{parsed.netloc}")


def _validate_sha(value: str) -> str:
    if not _SHA_RE.fullmatch(value):
        raise argparse.ArgumentTypeError("expected SHA must be a lowercase 40-character Git SHA")
    return value


def _request_url(origin: Origin, path: str, probe: str) -> str:
    encoded_probe = urllib.parse.quote(probe, safe="")
    return f"{origin.base_url}{path}?route_probe={encoded_probe}"


def _header(response: Response, name: str) -> str:
    value = response.headers.get(name)
    return "" if value is None else str(value).strip()


def _status(response: Response) -> int:
    status = getattr(response, "status", None)
    if status is None:
        status = response.getcode()
    return int(status)


def _get(
    *,
    opener: Opener,
    origin: Origin,
    path: str,
    probe: str,
    timeout: float,
) -> Response:
    request_url = _request_url(origin, path, probe)
    request = urllib.request.Request(
        request_url,
        method="GET",
        headers={"User-Agent": USER_AGENT},
    )
    try:
        response = opener.open(request, timeout=timeout)
    except urllib.error.HTTPError as exc:
        raise VerificationError(f"{origin.label} {path} returned HTTP {exc.code}") from None
    except (OSError, urllib.error.URLError) as exc:
        raise VerificationError(
            f"{origin.label} {path} transport failed ({type(exc).__name__})"
        ) from None

    status = _status(response)
    if status != 200:
        response.close()
        raise VerificationError(f"{origin.label} {path} returned HTTP {status}")
    if response.geturl() != request_url:
        response.close()
        raise VerificationError(f"{origin.label} {path} redirected")
    return response


def _read_response(response: Response) -> bytes:
    with response:
        return response.read()


def _verify_build_marker(
    *,
    opener: Opener,
    origin: Origin,
    expected_sha: str,
    probe: str,
    timeout: float,
) -> int:
    response = _get(
        opener=opener,
        origin=origin,
        path=BUILD_PATH,
        probe=probe,
        timeout=timeout,
    )
    body = _read_response(response)
    try:
        marker = json.loads(body)
    except (UnicodeDecodeError, json.JSONDecodeError, TypeError):
        raise VerificationError(
            f"{origin.label} {BUILD_PATH} was not a valid build marker"
        ) from None
    if marker != {"surface": "parents", "commit_sha": expected_sha}:
        raise VerificationError(f"{origin.label} {BUILD_PATH} served a stale build marker")
    return 200


def _verify_callback(
    *,
    opener: Opener,
    origin: Origin,
    probe: str,
    timeout: float,
) -> tuple[int, str, str]:
    response = _get(
        opener=opener,
        origin=origin,
        path=CALLBACK_PATH,
        probe=probe,
        timeout=timeout,
    )

    content_type = _header(response, "Content-Type").split(";", maxsplit=1)[0].lower()
    cache_control = _header(response, "Cache-Control").lower()
    referrer_policy = _header(response, "Referrer-Policy").lower()
    content_type_options = _header(response, "X-Content-Type-Options").lower()
    body = _read_response(response)

    if content_type != "text/html":
        raise VerificationError(f"{origin.label} {CALLBACK_PATH} was not text/html")
    if "no-store" not in {part.strip() for part in cache_control.split(",")}:
        raise VerificationError(f"{origin.label} {CALLBACK_PATH} did not disable storage")
    if referrer_policy != "no-referrer":
        raise VerificationError(f"{origin.label} {CALLBACK_PATH} did not disable referrers")
    if content_type_options != "nosniff":
        raise VerificationError(f"{origin.label} {CALLBACK_PATH} did not disable MIME sniffing")
    try:
        html = body.decode("utf-8")
    except UnicodeDecodeError:
        raise VerificationError(f"{origin.label} {CALLBACK_PATH} was not UTF-8 HTML") from None
    if CALLBACK_SENTINEL not in html:
        raise VerificationError(f"{origin.label} {CALLBACK_PATH} lacked the callback sentinel")

    return 200, content_type, hashlib.sha256(body).hexdigest()


def _write_evidence(path: Path, evidence: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(evidence, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def verify_parent_callback(
    *,
    expected_sha: str,
    origins: Sequence[Origin],
    expected_html: Path | None = None,
    evidence_path: Path | None = None,
    opener: Opener | None = None,
    timeout: float = 15.0,
    probe: str | None = None,
) -> dict[str, object]:
    """Verify callback routing and return sanitized operational evidence."""

    if not _SHA_RE.fullmatch(expected_sha):
        raise ValueError("expected_sha must be a lowercase 40-character Git SHA")
    if not origins:
        raise ValueError("at least one origin is required")
    if len({origin.label for origin in origins}) != len(origins):
        raise ValueError("origin labels must be unique")
    if len({origin.base_url for origin in origins}) != len(origins):
        raise ValueError("origin URLs must be unique")

    probe_value = probe or secrets.token_urlsafe(24).replace("=", "")
    if not _PROBE_RE.fullmatch(probe_value):
        raise ValueError("probe must contain 16-64 URL-safe characters")

    # Ignore ambient proxy configuration so a runner cannot add proxy
    # credentials to this deliberately unauthenticated promotion probe.
    active_opener = opener or cast(
        Opener,
        urllib.request.build_opener(
            urllib.request.ProxyHandler({}),
            _NoRedirectHandler(),
        ),
    )
    target_evidence: list[dict[str, object]] = []
    callback_hashes: list[str] = []

    for origin in origins:
        build_status = _verify_build_marker(
            opener=active_opener,
            origin=origin,
            expected_sha=expected_sha,
            probe=probe_value,
            timeout=timeout,
        )
        callback_status, content_type, callback_hash = _verify_callback(
            opener=active_opener,
            origin=origin,
            probe=probe_value,
            timeout=timeout,
        )
        callback_hashes.append(callback_hash)
        target_evidence.append(
            {
                "label": origin.label,
                "build_status": build_status,
                "callback_status": callback_status,
                "callback_content_type": content_type,
                "callback_artifact_sha256": callback_hash,
                "security_policy_verified": True,
            }
        )

    if len(set(callback_hashes)) != 1:
        raise VerificationError("parent callback artifacts differ across deployment targets")

    local_hash_match: bool | None = None
    if expected_html is not None:
        try:
            expected_body = expected_html.read_bytes()
        except OSError as exc:
            raise VerificationError(
                f"expected callback artifact could not be read ({type(exc).__name__})"
            ) from None
        if CALLBACK_SENTINEL.encode("utf-8") not in expected_body:
            raise VerificationError("expected callback artifact lacked the callback sentinel")
        expected_hash = hashlib.sha256(expected_body).hexdigest()
        local_hash_match = expected_hash == callback_hashes[0]
        if not local_hash_match:
            raise VerificationError("deployed callback differs from the expected callback artifact")

    evidence: dict[str, object] = {
        "schema_version": 1,
        "classification": "sanitized-operational-evidence",
        "result": "passed",
        "expected_commit_sha": expected_sha,
        "method": "GET",
        "paths": [BUILD_PATH, CALLBACK_PATH],
        "transport": {
            "authentication_sent": False,
            "cookies_sent": False,
            "javascript_used": False,
            "redirects_followed": False,
        },
        "target_count": len(target_evidence),
        "targets": target_evidence,
        "cross_target_artifact_match": True,
        "local_artifact_match": local_hash_match,
        "oauth_material_recorded": False,
    }
    if evidence_path is not None:
        _write_evidence(evidence_path, evidence)
    return evidence


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--expected-sha", required=True, type=_validate_sha)
    parser.add_argument(
        "--origin",
        action="append",
        required=True,
        type=_parse_origin,
        help="repeatable LABEL=https://host target",
    )
    parser.add_argument("--expected-html", type=Path)
    parser.add_argument("--evidence-path", type=Path)
    parser.add_argument("--timeout", type=float, default=15.0)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        evidence = verify_parent_callback(
            expected_sha=args.expected_sha,
            origins=args.origin,
            expected_html=args.expected_html,
            evidence_path=args.evidence_path,
            timeout=args.timeout,
        )
    except (ValueError, VerificationError) as exc:
        print(f"Parent callback verification failed: {exc}", file=sys.stderr)
        return 1
    print(
        f"Parent callback verification passed for {evidence['target_count']} deployment target(s)."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
