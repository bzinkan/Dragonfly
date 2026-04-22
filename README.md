# Dragonfly

Citizen science field app for kids 9–12. Every observation is real science via iNaturalist, fills a personal Dex, claims map territory, and earns standing in a class or friend group. Invite-only.

## Repo layout

```
backend/    FastAPI + Mangum (one Lambda serves all HTTP)
            Dispatcher-based observation handling.
lambdas/    Moderation, iNat submit, rarity refresh — separate Lambdas.
mobile/     Expo (React Native) — iOS, Android, web.
infra/      AWS CDK (Python). One cdk deploy per env.
content/    Expedition JSON. Source of truth; DynamoDB is a view.
scripts/    sync_expeditions, seed_dev_data, backfill_rarity, validate.
docs/       Architecture, data model, ADRs. Read these first.
```

## Getting started (Phase 0)

Prereqs: Python 3.12, Node 20, `uv`, AWS CLI configured, AWS CDK v2.

```bash
make install
make dev                    # FastAPI on :8080
curl localhost:8080/health
```

Deploy the data stack to your dev account:

```bash
cd infra
export DRAGONFLY_ENV=dev
uv run cdk bootstrap        # once per account/region
uv run cdk deploy --all
```

Phase 0 exit criterion: the Expo app shows the response from `/health` served by the deployed Lambda. That's it. Don't build Phase 1 features until this round-trip works.

## Where to look when

- **How a feature works end-to-end:** `docs/architecture.md`
- **What the DB looks like:** `docs/data-model.md`
- **How to add a reward type:** `docs/dispatcher.md`
- **How to write an expedition:** `docs/expedition-authoring.md`
- **What decision was made and why:** `docs/adr/`

## Current phase

Phase 1 (MVP). 10–12 weeks solo. See `docs/roadmap.md` for the week-by-week plan.
