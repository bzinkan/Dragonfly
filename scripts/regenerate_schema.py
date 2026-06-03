#!/usr/bin/env python
"""Regenerate JSON schemas under `content/schema/` from the Pydantic models.

Currently emits:
  * `content/schema/expedition.schema.json` from `app.models.expedition.Expedition`
  * `content/schema/sanctuary.schema.json`  from `app.models.sanctuary.SanctuaryConfig`

Idempotent. Running this twice with no model change leaves the files
byte-identical, so the CI step `git diff --exit-code` proves the
committed schemas match the source-of-truth Pydantic classes.

Authors run this whenever they touch `app.models.expedition` or
`app.models.sanctuary`.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from pydantic import BaseModel

_REPO_ROOT = Path(__file__).resolve().parent.parent
_BACKEND = _REPO_ROOT / "backend"
sys.path.insert(0, str(_BACKEND))

from app.models.expedition import Expedition  # noqa: E402
from app.models.sanctuary import SanctuaryConfig  # noqa: E402


def main() -> int:
    targets: tuple[tuple[type[BaseModel], str], ...] = (
        (Expedition, "expedition.schema.json"),
        (SanctuaryConfig, "sanctuary.schema.json"),
    )
    for model, filename in targets:
        schema = model.model_json_schema()
        out_path = _REPO_ROOT / "content" / "schema" / filename
        out_path.parent.mkdir(parents=True, exist_ok=True)
        # Stable formatting: sorted keys + 2-space indent + trailing newline.
        serialized = json.dumps(schema, indent=2, sort_keys=True) + "\n"
        out_path.write_text(serialized, encoding="utf-8")
        print(f"Wrote {out_path.relative_to(_REPO_ROOT)} ({len(serialized)} bytes)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
