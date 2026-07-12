from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest
from ulid import ULID

_ROOT = Path(__file__).resolve().parents[2]
_SCRIPT = _ROOT / "scripts/verify_deployed_dispatcher_benchmark.py"
_SPEC = importlib.util.spec_from_file_location("verify_deployed_dispatcher_benchmark", _SCRIPT)
assert _SPEC is not None and _SPEC.loader is not None
verifier = importlib.util.module_from_spec(_SPEC)
sys.modules[_SPEC.name] = verifier
_SPEC.loader.exec_module(verifier)


def _seed(count: int = 50) -> dict[str, object]:
    return {
        "result": "seeded",
        "started_at": "2026-07-12T12:00:00+00:00",
        "finished_at": "2026-07-12T12:05:00+00:00",
        "sample_count": count,
        "observation_ids": [str(ULID()) for _ in range(count)],
        "scenario_counts": {"unknown_no_location": count},
    }


def _rows(seed: dict[str, object], *, duration_ms: float = 150.0) -> list[dict[str, object]]:
    observation_ids = seed["observation_ids"]
    assert isinstance(observation_ids, list)
    return [
        {
            "observation_id": observation_id,
            "revision": "hinterland-api--0000045",
            "image": "hinterlandacrdev.azurecr.io/hinterland-api@sha256:" + "a" * 64,
            "method": "POST",
            "path": "/v1/observations",
            "duration_ms": duration_ms,
            "dispatch_status": "complete",
            "handler_durations_ms": {
                "dex": 1.0,
                "rarity": 2.0,
                "world": 3.0,
                "expedition": 4.0,
            },
        }
        for observation_id in observation_ids
    ]


def _evaluate(seed: dict[str, object], rows: list[dict[str, object]]) -> dict[str, object]:
    return verifier.evaluate_rows(
        seed=seed,
        rows=rows,
        expected_revision="hinterland-api--0000045",
        expected_image="hinterlandacrdev.azurecr.io/hinterland-api@sha256:" + "a" * 64,
        threshold_ms=300.0,
    )


def test_evaluate_rows_passes_exact_complete_sample_set() -> None:
    seed = _seed()
    evidence = _evaluate(seed, _rows(seed))

    assert evidence["result"] == "passed"
    assert evidence["observed_samples"] == 50
    assert evidence["p50_ms"] == 150.0
    assert evidence["p95_ms"] == 150.0
    assert evidence["handler_stats"]["expedition"] == {
        "samples": 50,
        "p50_ms": 4.0,
        "p95_ms": 4.0,
    }
    assert "observation_ids" not in evidence


def test_evaluate_rows_fails_closed_on_missing_duplicate_or_incomplete() -> None:
    seed = _seed(20)
    rows = _rows(seed)
    rows.pop()
    rows.append(dict(rows[0]))
    rows[0]["dispatch_status"] = "partial"

    evidence = _evaluate(seed, rows)

    assert evidence["result"] == "failed"
    assert set(evidence["failures"]) >= {
        "missing_dispatch_events",
        "duplicate_dispatch_events",
        "incomplete_dispatches",
    }


def test_evaluate_rows_uses_nearest_rank_and_fails_at_budget() -> None:
    seed = _seed(50)
    rows = _rows(seed, duration_ms=100.0)
    for row in rows[-3:]:
        row["duration_ms"] = 300.0

    evidence = _evaluate(seed, rows)

    assert evidence["p95_ms"] == 300.0
    assert evidence["threshold_exceed_count"] == 3
    assert "p95_budget_exceeded" in evidence["failures"]


def test_evaluate_rows_accepts_log_analytics_numeric_strings() -> None:
    seed = _seed(1)
    rows = _rows(seed)
    rows[0]["duration_ms"] = "664.72"
    rows[0]["handler_durations_ms"] = (
        '{"dex":55.92,"rarity":82.38,"world":82.72,"expedition":221.09}'
    )

    evidence = _evaluate(seed, rows)

    assert evidence["observed_samples"] == 1
    assert evidence["p95_ms"] == 664.72
    assert evidence["handler_stats"]["expedition"]["p95_ms"] == 221.09
    assert evidence["failures"] == ["p95_budget_exceeded"]


def test_evaluate_rows_rejects_invalid_seed_ids() -> None:
    seed = _seed(20)
    seed["observation_ids"] = ["not-an-ulid"] * 20

    with pytest.raises(ValueError, match="invalid or duplicate"):
        _evaluate(seed, [])
