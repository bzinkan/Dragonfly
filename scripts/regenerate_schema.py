#!/usr/bin/env python
"""Regenerate `content/schema/expedition.schema.json` from the Pydantic model.

Idempotent. Running this twice with no model change leaves the file
byte-identical, so the CI step `git diff --exit-code` proves the
committed schema matches the source-of-truth Pydantic class.

Authors run this whenever they touch `app.models.expedition`.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
_BACKEND = _REPO_ROOT / "backend"
sys.path.insert(0, str(_BACKEND))

from app.models.expedition import Expedition  # noqa: E402


def main() -> int:
    schema = Expedition.model_json_schema()
    out_path = _REPO_ROOT / "content" / "schema" / "expedition.schema.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    # Stable formatting: sorted keys + 2-space indent + trailing newline.
    serialized = json.dumps(schema, indent=2, sort_keys=True) + "\n"
    out_path.write_text(serialized, encoding="utf-8")
    print(f"Wrote {out_path.relative_to(_REPO_ROOT)} ({len(serialized)} bytes)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
