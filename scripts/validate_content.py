#!/usr/bin/env python
"""Validate every JSON file under content/expeditions/.

Exits 0 if all files parse against `app.models.expedition.Expedition`.
Exits 1 with a per-file report otherwise.

The CI workflow `.github/workflows/content-validate.yml` runs this on
every PR that touches `content/**` or the model itself. Authors run
`make validate-content` locally before pushing.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from pydantic import ValidationError

# Path manipulation so the script works whether invoked from repo root
# or from backend/ (CI uses the latter).
_REPO_ROOT = Path(__file__).resolve().parent.parent
_BACKEND = _REPO_ROOT / "backend"
sys.path.insert(0, str(_BACKEND))

from app.models.expedition import Expedition  # noqa: E402


def main() -> int:
    content_root = _REPO_ROOT / "content" / "expeditions"
    if not content_root.exists():
        print(f"No expedition content found at {content_root}; nothing to validate.")
        return 0

    failures: list[tuple[Path, str]] = []
    files = sorted(content_root.rglob("*.json"))
    if not files:
        print(f"No expedition JSON files in {content_root}; nothing to validate.")
        return 0

    for path in files:
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            failures.append((path, f"invalid JSON: {exc}"))
            continue

        try:
            exp = Expedition.model_validate(data)
        except ValidationError as exc:
            failures.append((path, f"schema mismatch:\n{exc}"))
            continue

        # Filename stem must equal the expedition id.
        if path.stem != exp.id:
            failures.append(
                (path, f"filename stem '{path.stem}' must equal id '{exp.id}'")
            )

    if failures:
        print(f"\n{len(failures)} expedition file(s) failed validation:\n")
        for path, message in failures:
            print(f"  - {path.relative_to(_REPO_ROOT)}")
            for line in str(message).splitlines():
                print(f"      {line}")
        return 1

    print(f"OK: {len(files)} expedition file(s) validated.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
