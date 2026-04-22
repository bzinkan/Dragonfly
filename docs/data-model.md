# Data Model

Single-table DynamoDB. Table name: `Dragonfly`. Two global secondary indexes: `GSI1`, `GSI2`. Two base attributes: `PK`, `SK`. Everything else is entity-specific.

## Why single-table

Every access pattern Dragonfly has is a lookup by a known key or a range query within a known parent. A kid's Dex is all items under their `USER#` partition with `SK begins_with DEX#`. A group's leaderboard is all membership rows under the group. There are no cross-entity joins, no "give me all observations where species is rare" scans. A single table with well-designed keys serves every read in Phase 1–4 with one query.

The mental model: **`PK` scopes the partition, `SK` orders items within it, GSIs exist only for the access patterns that don't fit that shape.**

## Key schema

| Entity          | PK                     | SK                          | GSI1PK              | GSI1SK                   | GSI2PK              | GSI2SK                     |
|-----------------|------------------------|-----------------------------|---------------------|--------------------------|---------------------|----------------------------|
| User            | `USER#<id>`            | `PROFILE`                   | `EMAIL#<email>`     | `USER#<id>`              | —                   | —                          |
| Group           | `GROUP#<id>`           | `META`                      | `CODE#<joinCode>`   | `GROUP#<id>`             | —                   | —                          |
| Membership      | `GROUP#<id>`           | `MEMBER#<userId>`           | `USER#<userId>`     | `GROUP#<id>`             | —                   | —                          |
| Observation     | `USER#<userId>`        | `OBS#<ts>#<obsId>`          | `GROUP#<groupId>`   | `OBS#<ts>`               | `SPECIES#<taxonId>` | `USER#<userId>#<ts>`       |
| Dex entry       | `USER#<userId>`        | `DEX#<taxonId>`             | —                   | —                        | —                   | —                          |
| Expedition prog.| `USER#<userId>`        | `EXP#<expId>`               | —                   | —                        | —                   | —                          |
| Species cache   | `SPECIES#<taxonId>`    | `META`                      | —                   | —                        | —                   | —                          |
| Region meta     | `REGION#<geohash4>`    | `META`                      | —                   | —                        | —                   | —                          |
| Rarity entry    | `REGION#<geohash4>`    | `SPECIES#<taxonId>`         | —                   | —                        | —                   | —                          |
| Reverse geocode | `GEO#<rlat>#<rlng>`    | `REVERSE`                   | —                   | —                        | —                   | —                          |
| Places cache    | `GEO#<rlat>#<rlng>`    | `PLACES#<environment>`      | —                   | —                        | —                   | —                          |
| Review queue    | `GROUP#<groupId>`      | `REVIEW#<ts>#<obsId>`       | `STATUS#<status>`   | `REVIEW#<ts>`            | —                   | —                          |
| Job state       | `JOB#<jobName>`        | `STATE`                     | —                   | —                        | —                   | —                          |

Timestamps (`<ts>`) are ISO-8601 strings; they sort lexically. Observation IDs and user IDs are ULIDs. Join codes are 6 upper-case alphanumerics. Geocache coordinates (`<rlat>`, `<rlng>`) are raw lat/lng rounded to 4 decimal places (~11m precision), stored as fixed-width strings with a leading sign (e.g. `+40.7128#-074.0060`), so near-duplicate calls from the same neighborhood hit cache. See ADR 0003.

## Access patterns

Every supported read, mapped to the key that serves it:

| Access pattern                                   | How                                                          |
|--------------------------------------------------|--------------------------------------------------------------|
| Get user by id                                   | `GetItem(USER#<id>, PROFILE)`                                |
| Find user by email                               | `Query GSI1 where GSI1PK=EMAIL#<email>`                      |
| Get group metadata                               | `GetItem(GROUP#<id>, META)`                                  |
| Resolve join code → group                        | `Query GSI1 where GSI1PK=CODE#<code>`                        |
| List group members (+ counts for leaderboard)    | `Query PK=GROUP#<id>, SK begins_with MEMBER#`                |
| List groups a user belongs to                    | `Query GSI1 where GSI1PK=USER#<id>, GSI1SK begins_with GROUP#` |
| List a user's observations (newest first)        | `Query PK=USER#<id>, SK begins_with OBS#, ScanIndexForward=false` |
| List a group's observations (newest first)       | `Query GSI1 where GSI1PK=GROUP#<id>, GSI1SK begins_with OBS#, ScanIndexForward=false` |
| "Who else found this species?" (group scope)     | `Query GSI2 where GSI2PK=SPECIES#<taxonId>`, filter in-app   |
| A user's full Dex                                | `Query PK=USER#<id>, SK begins_with DEX#`                    |
| Is this a first find for this user?              | `PutItem(PK=USER#<id>, SK=DEX#<taxonId>, ConditionExpression=attribute_not_exists)` |
| Expedition progress for a user                   | `Query PK=USER#<id>, SK begins_with EXP#`                    |
| Get species info (cached from iNat taxa)         | `GetItem(SPECIES#<taxonId>, META)`                           |
| Rarity tier for (region, species)                | `GetItem(REGION#<gh>, SPECIES#<taxonId>)`                    |
| All species known in a region (rare nightly job) | `Query PK=REGION#<gh>, SK begins_with SPECIES#`              |
| Cached reverse geocode for coords                | `GetItem(GEO#<rlat>#<rlng>, REVERSE)`                        |
| Cached nearby places for an onboarding environment | `GetItem(GEO#<rlat>#<rlng>, PLACES#<env>)`                 |
| Pending review items for a group                 | `Query PK=GROUP#<id>, SK begins_with REVIEW#`                |
| Review items by status across all groups (admin) | `Query GSI1 where GSI1PK=STATUS#pending`                     |
| Resume a stalled rarity job                      | `GetItem(JOB#rarity, STATE)`                                 |

If an access pattern isn't on this list, it requires an ADR before it gets added. Adding indexes later is cheap in DynamoDB but retrofitting key prefixes is not.

## Denormalization strategy

Counters live on the membership row, not computed at read time:

```
PK=GROUP#<gid>  SK=MEMBER#<uid>
    observation_count: 47
    dex_count: 31
    rarest_tier: "legendary"
    last_obs_at: "2025-10-14T12:34:56Z"
```

These are updated in the same transaction as the observation insert, via `UpdateItem` with `ADD` on the counter attributes. The leaderboard is then a single `Query` on the group partition, sorted in memory by `observation_count` (usually < 100 members). No aggregation job, no eventual consistency window.

Same pattern for the species cache: when an observation lands, if `SPECIES#<taxonId>/META` doesn't exist, fetch from iNat `/v1/taxa/<id>` and write it once. Subsequent observations of the same species hit the cache. Species rarely change; a TTL of 90 days is plenty.

## Geocache partition

The `GEO#<rlat>#<rlng>` partition caches Google Maps Platform data-API responses, per ADR 0003. Two SK patterns share the partition:

- `REVERSE` — cached reverse-geocode result for the rounded coordinates. Written once when the first observation at these coordinates is geocoded; read on subsequent observations to avoid re-paying Google. The result is *also* denormalized onto the `OBS#` row so rendering a single observation doesn't require a second `GetItem`.
- `PLACES#<environment>` — cached Places Nearby Search result for the coordinates, filtered by the kid's picked environment (`park`, `yard`, etc.). TTL of 7 days via DynamoDB's TTL attribute.

Both rows carry a `ttl` attribute (epoch seconds). DynamoDB's TTL is a soft guarantee — rows can linger past expiry before sweep — which is fine because the cache-miss path re-fetches and overwrites.

Rounding rule: raw lat/lng is rounded to 4 decimal places (~11m precision) and formatted with an explicit sign. `40.71281, -74.00602` becomes `GEO#+40.7128#-074.0060`. The explicit sign keeps the key lexically unambiguous and the fixed width keeps cache keys from colliding across hemispheres.

## First-find detection

The single line of code that drives the celebration:

```python
try:
    table.put_item(
        Item={
            "PK": f"USER#{user_id}",
            "SK": f"DEX#{taxon_id}",
            "first_observed_at": iso_now(),
            "first_obs_id": obs_id,
        },
        ConditionExpression="attribute_not_exists(PK)",
    )
    is_first_find = True
except ClientError as e:
    if e.response["Error"]["Code"] == "ConditionalCheckFailedException":
        is_first_find = False
    else:
        raise
```

No read-then-write. No race. The DB tells you whether this is the first time this user has logged this species, atomically.

## Transactional writes

Observation submission is two DynamoDB operations, not one. See ADR 0004 for the reasoning — the short version is that first-find detection requires a conditional write that can fail independently of the observation write, and `TransactWriteItems`' all-or-nothing semantics can't express that.

**Step 1 — submission transaction.** `TransactWriteItems` with exactly two ops, atomic:

1. `Put` the `OBS#` row.
2. `Update` the `MEMBER#` row: `ADD observation_count :one, SET last_obs_at = :now`.

This guarantees the invariant a user can actually perceive: observation_count never diverges from the count of actual observation rows. Transactions cost 2x write units; at this scale the consistency is cheap.

**Step 2 — dispatcher handlers.** After the transaction commits, the dispatcher runs. Two handlers issue additional writes to `MEMBER#`:

- `DexHandler` does the conditional `PutItem` on `DEX#<taxonId>` (the first-find detector — see [First-find detection](#first-find-detection) below). On success, it follows with `UpdateItem` on `MEMBER#`: `ADD dex_count :one`.
- `RarityHandler` does a conditional `UpdateItem` on `MEMBER#` to set `rarest_tier` if this observation outranks the previous best.

These are not atomic with each other or with the submission transaction. DynamoDB's `ADD` is commutative so there's no lost-update hazard; a reader hitting `MEMBER#` mid-dispatch may briefly see an intermediate state (observation_count updated, dex_count not yet). The leaderboard tolerates this — it's already eventually consistent from the client's perspective.

If the Lambda crashes between step 1 and step 2, the observation exists but its Dex entry and counters do not. See `docs/runbook.md` for the replay recovery workflow.

## Capacity model

Start on-demand billing. Do not provision capacity until you have at least 1000 daily active users and a month of CloudWatch data to model against. The overhead of auto-scaling tuning at this stage is pure distraction.

GSI2 (the species-wide index) has higher write amplification because every observation writes to it. Keep an eye on its consumed write units once you're past 10k observations/day — that's the first index to consider splitting or making sparse.

## Migration strategy

Two rules:

1. **Key prefixes are forever.** Don't rename `USER#` to `U#` to save bytes. The cost of a table migration dwarfs any storage savings you'd see in the first three years.
2. **New attributes are free; removed attributes are not.** When you stop using an attribute, leave it in place on old rows. Schema is client-side in DynamoDB; Pydantic models evolve, the rows don't need to.

When you genuinely need a schema change (e.g. adding a new entity type), the workflow is: deploy code that writes to the new shape and reads either, backfill via a script in `scripts/`, deploy code that only reads the new shape, delete the old rows. Never combine these steps.

## Local development

DynamoDB Local via `scripts/local_dev.sh` (docker-compose). `boto3` clients point at `http://localhost:8000` when `DRAGONFLY_ENV=local`. `scripts/seed_dev_data.py` creates a test group, two parents, four kids, and 50 observations across five species — enough to make the Dex and leaderboard feel real while developing.

The key schema is identical between local and cloud. There is no "local-only" deviation. If something works locally and fails in the cloud, it's a permissions or IAM issue, never a schema issue.
