#!/usr/bin/env python
"""Author-time expedition draft scaffold generator.

This is deliberately author-time only. It does not run from the backend,
does not import any agent framework, and does not make network calls. Authors
can use the generated JSON as a starting point, edit it, then validate with
``python scripts/validate_content.py``.

Examples:
    python scripts/draft_expedition.py "city park insects" --environment park
    python scripts/draft_expedition.py "schoolyard trees" --id schoolyard_trees --out content/expeditions/starters/schoolyard_trees.json
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from app.models.expedition import Expedition  # noqa: E402

_ENVIRONMENTS = ("yard", "park", "street", "school", "other")


def _slug(text: str) -> str:
    cleaned = re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")
    cleaned = re.sub(r"_+", "_", cleaned)
    return cleaned[:48].strip("_") or "draft_expedition"


def _title(text: str) -> str:
    words = re.sub(r"[_-]+", " ", text).strip().split()
    if not words:
        return "Draft Expedition"
    titled = " ".join(w.capitalize() for w in words)
    return titled[:80]


def _draft(args: argparse.Namespace) -> dict[str, Any]:
    expedition_id = args.id or _slug(args.prompt)
    title = args.title or _title(args.prompt)
    environment = args.environment
    return {
        "id": expedition_id,
        "title": title,
        "subtitle": "A reviewed author-time draft. Edit before publishing.",
        "tier": args.tier,
        "duration_minutes": args.duration_minutes,
        "environments": [environment],
        "intro": (
            "Take your time and look closely. Every step should use a real "
            "outdoor observation, not a staged photo."
        ),
        "outro": "Nice field work. Your observations are now part of your Dex.",
        "prerequisites": [],
        "steps": [
            {
                "id": "first_observation",
                "description": "Find one living thing that catches your eye.",
                "match": {"kind": "any_organism"},
                "hint": "Plants, insects, birds, fungi, and tracks all count.",
            },
            {
                "id": "new_to_you",
                "description": "Find something that is not already in your Dex.",
                "match": {"kind": "not_in_dex"},
                "hint": "Look under leaves, along edges, or near a different plant.",
            },
            {
                "id": "different_spot",
                "description": "Make an observation from a different nearby spot.",
                "match": {
                    "kind": "not_within_radius_of_existing",
                    "radius_meters": 25,
                },
                "hint": "Move a short walk away and look again.",
            },
        ],
    }


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("prompt", help="Short theme prompt for the expedition.")
    parser.add_argument("--id", help="Snake-case expedition id. Defaults to a slug.")
    parser.add_argument("--title", help="Display title. Defaults to title-cased prompt.")
    parser.add_argument("--tier", type=int, default=1, choices=range(1, 6))
    parser.add_argument("--duration-minutes", type=int, default=20)
    parser.add_argument("--environment", choices=_ENVIRONMENTS, default="other")
    parser.add_argument("--out", type=Path, help="Optional output JSON path.")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    draft = _draft(args)
    expedition = Expedition.model_validate(draft)
    rendered = json.dumps(
        expedition.model_dump(mode="json", exclude_none=True),
        indent=2,
        sort_keys=False,
    )

    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(rendered + "\n", encoding="utf-8")
        print(f"Wrote {args.out}")
    else:
        print(rendered)
    return 0


if __name__ == "__main__":
    sys.exit(main())
