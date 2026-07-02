"""Tests for admin/expedition_funnel.py.

`summarize` is a pure function over (progress, content) pairs, so the
tests feed it in-memory ORM rows directly -- no session mocking. The
`--days` window is applied in SQL by `load_pairs`, not by `summarize`,
so there is nothing to test for it here.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from admin.expedition_funnel import summarize
from app.db import models

_STARTED_AT = datetime(2026, 5, 10, 12, 0, 0, tzinfo=UTC)


def _exp_body(*, exp_id: str, tier: int = 1, steps_count: int = 1) -> dict[str, Any]:
    return {
        "id": exp_id,
        "title": f"Test {exp_id}",
        "tier": tier,
        "duration_minutes": 20,
        "environments": ["yard"],
        "intro": "Find some things.",
        "outro": "Real science.",
        "prerequisites": [],
        "steps": [
            {"id": f"s{i}", "description": "x", "match": {"kind": "any_organism"}}
            for i in range(steps_count)
        ],
    }


def _content(exp_id: str, body: dict[str, Any]) -> models.ExpeditionContent:
    return models.ExpeditionContent(
        id=exp_id, tier=body.get("tier", 1), content_hash="x", body=body, archived=False
    )


def _progress_row(
    exp_id: str,
    *,
    completed_steps: dict[str, Any],
    completed_at: datetime | None = None,
    created_at: datetime = _STARTED_AT,
) -> models.ExpeditionProgress:
    progress = models.ExpeditionProgress(
        id=f"prog-{exp_id}-{id(completed_steps)}",
        user_id="01J0KIDID0000000000000ULID",
        group_id="01J0GROUPID00000000000ULID",
        expedition_id=exp_id,
        completed_steps=completed_steps,
        completed_at=completed_at,
    )
    progress.created_at = created_at
    return progress


def test_summarize_empty_input() -> None:
    assert summarize([]) == []


def test_summarize_mixed_rows_one_expedition() -> None:
    """Never-advanced, mid-run (dict values), and completed (legacy
    string values) rows roll up into one FunnelRow with per-step counts
    in content order."""
    content = _content("backyard_starter", _exp_body(exp_id="backyard_starter", steps_count=3))
    never_advanced = _progress_row("backyard_starter", completed_steps={})
    mid_run = _progress_row(
        "backyard_starter",
        completed_steps={
            "s0": {
                "completed_at": "2026-05-10T13:00:00+00:00",
                "observation_id": "01J0OBSID0000000000000ULID",
            }
        },
    )
    finished = _progress_row(
        "backyard_starter",
        completed_steps={
            "s0": "2026-05-10T13:00:00+00:00",
            "s1": "2026-05-10T13:30:00+00:00",
            "s2": "2026-05-10T14:00:00+00:00",
        },
        completed_at=_STARTED_AT + timedelta(minutes=120),
    )

    rows = summarize([(never_advanced, content), (mid_run, content), (finished, content)])

    assert len(rows) == 1
    row = rows[0]
    assert row.expedition_id == "backyard_starter"
    assert row.title == "Test backyard_starter"
    assert row.starts == 3
    assert row.advanced == 2
    assert row.completed == 1
    assert row.advance_rate == 2 / 3
    assert row.completion_rate == 1 / 3
    assert row.step_counts == (("s0", 2), ("s1", 1), ("s2", 1))
    assert row.median_minutes_to_complete == 120.0


def test_summarize_counts_orphaned_keys() -> None:
    """Keys the current content no longer has (content edits) don't get
    per-step rows but do show in a trailing orphaned_keys total."""
    content = _content("x", _exp_body(exp_id="x", steps_count=1))
    row_a = _progress_row(
        "x",
        completed_steps={
            "s0": "2026-05-10T13:00:00+00:00",
            "old_step": "2026-05-10T13:05:00+00:00",
        },
    )
    row_b = _progress_row("x", completed_steps={"gone_too": "2026-05-10T13:10:00+00:00"})

    rows = summarize([(row_a, content), (row_b, content)])

    assert rows[0].step_counts == (("s0", 1), ("orphaned_keys", 2))


def test_summarize_bad_content_falls_back_to_stored_keys() -> None:
    """An unvalidatable body must not crash the report: the id stands in
    for the title and step order falls back to sorted stored keys."""
    content = models.ExpeditionContent(
        id="x", tier=1, content_hash="x", body={"not": "valid"}, archived=False
    )
    progress = _progress_row(
        "x",
        completed_steps={
            "b_step": "2026-05-10T13:00:00+00:00",
            "a_step": "2026-05-10T12:30:00+00:00",
        },
    )

    rows = summarize([(progress, content)])

    assert len(rows) == 1
    row = rows[0]
    assert row.title == "x"
    assert row.starts == 1
    assert row.advanced == 1
    assert row.completed == 0
    assert row.median_minutes_to_complete is None
    # Sorted stored keys, and nothing counts as orphaned.
    assert row.step_counts == (("a_step", 1), ("b_step", 1))


def test_summarize_median_over_two_completed_rows() -> None:
    content = _content("x", _exp_body(exp_id="x", steps_count=1))
    fast = _progress_row(
        "x",
        completed_steps={"s0": "2026-05-10T12:10:00+00:00"},
        completed_at=_STARTED_AT + timedelta(minutes=10),
    )
    slow = _progress_row(
        "x",
        completed_steps={"s0": "2026-05-10T12:30:00+00:00"},
        completed_at=_STARTED_AT + timedelta(minutes=30),
    )

    rows = summarize([(fast, content), (slow, content)])

    assert rows[0].median_minutes_to_complete == 20.0


def test_summarize_sorts_by_tier_then_id() -> None:
    tier_two = _content("aaa", _exp_body(exp_id="aaa", tier=2))
    tier_one = _content("zzz", _exp_body(exp_id="zzz", tier=1))
    rows = summarize(
        [
            (_progress_row("aaa", completed_steps={}), tier_two),
            (_progress_row("zzz", completed_steps={}), tier_one),
        ]
    )
    assert [row.expedition_id for row in rows] == ["zzz", "aaa"]
