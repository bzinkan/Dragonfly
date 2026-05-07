# Postgres Data Model

ADR 0005 supersedes the original DynamoDB single-table design. Dragonfly now
uses Cloud SQL for PostgreSQL as the operational store.

The logical product invariants are unchanged:

- first-find detection is atomic
- leaderboard counters live on membership rows
- expedition JSON in git is source of truth
- slow integrations do not block kid-facing submission success
- dispatcher handlers do not call external APIs

## Core Tables

| Table | Purpose |
|---|---|
| `users` | Firebase-backed parent, teacher, and kid identities |
| `groups` | Invite-only class/family groups with join codes |
| `memberships` | User membership plus leaderboard counters |
| `photos` | GCS object lifecycle state |
| `observations` | Kid observations and denormalized display fields |
| `dex_entries` | First species finds per user |
| `expedition_content` | Materialized view of repo-authored expedition JSON |
| `expedition_progress` | Per-user progress through active expeditions |
| `review_queue` | Teacher/adult review for quarantined photos |
| `ingest_runs` | Replayable ingest audit and cursor state |
| `job_state` | Durable cursors for scheduled/background jobs |
| `species_cache` | Cached iNaturalist taxa metadata |
| `geo_cache` | Cached reverse geocode and nearby-place data |
| `rarity_cache` | Regional rarity tiers consumed by `RarityHandler` |

## Access Patterns

| Access pattern | SQL shape |
|---|---|
| Load current user | `select * from users where firebase_uid = $1` |
| Load group members | `select * from memberships where group_id = $1` |
| Group leaderboard | `select * from memberships where group_id = $1 order by dex_count desc` |
| User observations | `select * from observations where user_id = $1 order by created_at desc` |
| Group observations | `select * from observations where group_id = $1 order by created_at desc` |
| User Dex | `select * from dex_entries where user_id = $1 order by first_seen_at desc` |
| First find | `insert into dex_entries (...) on conflict (user_id, taxon_id) do nothing` |
| Expedition progress | `select * from expedition_progress where user_id = $1` |
| Review queue | `select * from review_queue where group_id = $1 and status = 'pending'` |
| Rarity lookup | `select * from rarity_cache where region_geohash = $1 and taxon_id = $2` |
| Ingest replay | `select * from ingest_runs where source = $1 and status = 'failed'` |

## Atomic Submission Transaction

`POST /v1/observations` must commit the core product state in one transaction:

1. Insert the observation row.
2. Update the membership observation counter.
3. Attempt `dex_entries` insert with `ON CONFLICT DO NOTHING`.
4. If the insert wins, update the membership Dex counter.
5. Run deterministic dispatcher handlers against already-persisted state.
6. Store reward output on the observation row.
7. Enqueue async work for iNaturalist submission and other slow tasks.

The first-find check must not become read-then-write. The database unique
constraint is the source of truth under concurrency.

## Ingest And Cursors

`ingest_runs` is the operational record for replayable data movement. Content
sync, taxa refresh, rarity snapshots, moderation events, and telemetry-derived
jobs all write run state before mutating durable app data.

Failed ingest runs are replayed by source and cursor. Replays must be
idempotent and must not duplicate observations, Dex rows, expedition rows, or
review queue items.

## Local Development

Local development uses `backend/compose.yaml` Postgres and Alembic:

```bash
make dev-db
make db-migrate
make dev
curl localhost:8080/ready
```
