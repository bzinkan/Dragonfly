# Risk 0004: Expedition authoring tool was a stub

- **Status:** Resolved
- **Date filed:** 2026-05-10
- **Resolved:** 2026-06-04
- **Owner:** Brian

## Resolution

`scripts/draft_expedition.py` now generates a schema-valid expedition JSON
scaffold from a short prompt:

```bash
python scripts/draft_expedition.py "city park insects" --environment park
```

It is intentionally author-time only:

- no backend import path
- no API route
- no network call
- no agent framework
- no kid-facing runtime LLM

The generated draft is validated through `Expedition.model_validate` before it
is printed or written. Authors still review/edit the JSON, run
`python scripts/validate_content.py`, and commit the final content.

## Future Enhancement

A provider-backed LLM drafting mode can be added later if Brian explicitly
chooses a provider and budget. That would be a convenience feature, not a beta
blocker.
