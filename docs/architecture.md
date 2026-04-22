# Architecture

## System at a glance

Dragonfly is a serverless app built around one synchronous request path (observation submission) and two asynchronous workers (photo moderation, rarity cache refresh). Everything else — Dex, leaderboard, expeditions — is derived data computed at submission time and cached.

```
┌─────────────────┐
│  Expo client    │  iOS / Android / web
│  (React Native) │
└────────┬────────┘
         │ HTTPS (JWT)
         ▼
┌─────────────────┐      ┌──────────────┐
│  API Gateway    │─────▶│   Cognito    │  (auth)
└────────┬────────┘      └──────────────┘
         │
         ▼
┌─────────────────┐
│  FastAPI on     │   the one Lambda that handles all HTTP.
│  Lambda (Mangum)│   Stateless. Reads/writes DynamoDB and S3.
└────────┬────────┘
         │
         ├──────────────▶  DynamoDB (single table: Dragonfly)
         ├──────────────▶  S3 (photos, presigned upload URLs)
         ├──────────────▶  iNaturalist API (CV + project submit)
         └──────────────▶  SQS (hands off async work)
                              │
                              ▼
                 ┌────────────────────────┐
                 │  Worker Lambdas        │
                 │  ─ moderation (S3 ⟶ Rekognition)
                 │  ─ inat_submit (SQS consumer)
                 │  ─ rarity_refresh (EventBridge cron)
                 └────────────────────────┘
```

## The one important request path

An observation submission is the hot path. Everything that matters — first-find celebration, expedition progress, leaderboard updates, rarity tier — is computed here, in this order:

1. Client uploads photo to S3 `pending/` prefix via presigned URL.
2. Client calls `POST /observations` with `{ photo_key, lat, lng, taxon_id, ... }`.
3. API Lambda validates, writes the `OBS#` row to DynamoDB.
4. **Dispatcher runs.** The `Context` object (db, user, group, observation, location) is passed through every handler in `HANDLERS`. Each returns zero or more `Reward`s.
5. Rewards are returned to the client, sorted by weight desc. The client renders the celebration sequence from that list.
6. An SQS message is enqueued for `inat_submit` to push to iNaturalist out of band.
7. Moderation runs on the S3 side, independently — if a photo is flagged post-submission, the observation is moved to quarantine and the teacher review queue picks it up.

The client never knows or cares which handler produced which reward. Adding Territory in Phase 2, Seasons in Phase 3, Missions in Phase 4 is purely additive on the server.

## Component responsibilities

**API Lambda (FastAPI + Mangum).** All synchronous HTTP. Owns the dispatcher. Must respond inside API Gateway's 29s timeout — aim for p95 < 500ms. No blocking iNat calls on the hot path; that's what SQS is for.

**Moderation Lambda.** Triggered by `s3:ObjectCreated:*` on the `pending/` prefix. Calls Rekognition `DetectModerationLabels`. Clean photos are copied to `observations/`; flagged photos go to `quarantine/` and write a `REVIEW#` row. See `moderation.md`.

**iNat Submit Lambda.** SQS consumer. Handles retries, dedup via idempotency key (observation id), and writes the returned iNat observation id back onto the `OBS#` row. On terminal failure (e.g. iNat down for > 24h), moves the message to a DLQ and alarms.

**Rarity Refresh Lambda.** EventBridge cron at 03:00 UTC. Self-continues via a `JOB#rarity` cursor row if it runs out of time. Never parallelizes — iNat rate limits matter more than throughput. See `rarity-pipeline.md`.

## External dependencies and failure modes

| Dependency | Used for | Failure mode |
|---|---|---|
| iNaturalist CV | Species ID on upload | Fallback: let kid free-text select; log `cv_unavailable` flag on the observation |
| iNaturalist submit | Scientific contribution | Queue retries; kid sees success regardless (we own the project account) |
| AWS Rekognition | Photo moderation | If API errors, hold in `pending/` and retry with exponential backoff; do not default-allow |
| USA-NPN (Phase 3) | Phenology windows | Weekly sync to local cache; offline-first |

The app must degrade gracefully on all of these. The kid experience cannot depend on iNat or NPN being reachable at the moment of submission.

## Auth model

Cognito user pool with a custom `role` attribute (`parent` | `teacher` | `kid`) and a `group_id` attribute added on join. JWT verified on every API request via the `core/auth.py` dependency. Kids under 13 have no email — they authenticate via a group join code exchanged for a Cognito account created by the parent/teacher at join time.

One iNaturalist account is owned by the app (the "project account"). All observations are submitted as that account, tagged with our project. Kids do not have iNat accounts until they turn 13 and opt into the claim flow (Phase 3).

## Deployment

AWS CDK in Python, one `cdk deploy` per environment. Environments: `dev` (personal AWS account), `staging` (one shared), `prod`. GitHub Actions deploys on merge to `main` for `dev`; `staging` and `prod` are manual-approve workflows.

Secrets: Cognito user pool ID, iNat project account credentials, and the Rekognition thresholds live in AWS Systems Manager Parameter Store, loaded at Lambda cold start via `pydantic-settings`. Never commit secrets. Never pass secrets via Lambda environment variables in `dev` even — the habit matters.

## Observability

Structured JSON logs from every Lambda, shipped to CloudWatch. One log line per observation submission that includes: `observation_id`, `user_id`, `group_id`, `handler_rewards` (list), `dispatcher_duration_ms`, `taxon_id`. That single line is enough to debug 80% of "why didn't I get a celebration" complaints.

CloudWatch alarms on: API 5xx rate > 1%, moderation DLQ depth > 0, rarity job duration > 12 min, iNat submit DLQ depth > 0. Everything else is a dashboard, not an alarm.

## Key invariants (things to preserve through all four phases)

1. **The submission endpoint never changes shape.** Handlers are added; the endpoint is not modified.
2. **Expedition JSON is the source of truth.** DynamoDB is a materialized view of `content/expeditions/`. A deploy is the only write path.
3. **Conditional `PutItem` is how first-find is detected.** Don't add a read-then-write pattern; it introduces a race.
4. **Moderation happens in S3, not in the API Lambda.** The API path must not block on Rekognition.
5. **Denormalized counters on membership rows are the leaderboard.** Don't aggregate at read time.
