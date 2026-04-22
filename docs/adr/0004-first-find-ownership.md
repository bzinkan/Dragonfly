# ADR 0004: First-find detection owns its own write

- **Status:** Accepted
- **Date:** 2026-04-22
- **Deciders:** Solo author
- **Supersedes:** —
- **Related:** ADR 0001 (single-table DynamoDB); reconciles `docs/data-model.md` and `docs/dispatcher.md`

## Context

Two normative docs gave conflicting instructions for how first-find detection — the atomic check that a user has never logged this species before — fits into the observation submission flow.

`docs/data-model.md` described observation submission as a single `TransactWriteItems` with three operations: `Put` the `OBS#` row, `Update` the `MEMBER#` row (`ADD observation_count :one` plus `ADD dex_count :one` if first-find), and `Put` the `DEX#` row with `ConditionExpression="attribute_not_exists(PK)"`.

`docs/dispatcher.md` described first-find detection as `DexHandler.handle`'s responsibility, using the same conditional `PutItem` on the `DEX#` row, with the `is_first_find` boolean flowing from that call into `ctx.results["dex"].state` for downstream handlers.

Both cannot be true. If the transaction writes the `DEX#` row, the handler's subsequent conditional put always fails (row already exists) and `is_first_find` is always false. If the handler writes it, the transaction doesn't — and the `MEMBER#` update inside the transaction can't branch on a flag that hasn't been computed yet.

A deeper point: even if we pre-computed `is_first_find` and tried to put all three ops in one `TransactWriteItems`, the transaction semantics fight us. `TransactWriteItems` is all-or-nothing — the condition on the `DEX#` put gates the entire transaction, so on a repeat-find the `OBS#` write and `observation_count` increment would also fail. That's the opposite of what we want. On a repeat-find, we want observation_count to bump; we just don't want dex_count to bump.

## Decision

**First-find is detected by `DexHandler` with a conditional `PutItem` on the `DEX#` row, and the handler owns both the write and the downstream `dex_count` increment.**

Observation submission is therefore split into two DynamoDB operations, both executed before the dispatcher returns to the client:

1. **Submission transaction** — `TransactWriteItems` with exactly two ops:
   - `Put` the `OBS#` row.
   - `Update` the `MEMBER#` row: `ADD observation_count :one, SET last_obs_at = :now`.

   Atomicity here guarantees a kid never sees their observation count bump without the observation existing, or vice versa. This is the consistency property that actually matters to the UI.

2. **Dispatcher** runs `HANDLERS` in order. `DexHandler` runs first and attempts the conditional `PutItem` on `DEX#<taxonId>`:
   - Success → `is_first_find = True`. Handler issues a second `UpdateItem` on the `MEMBER#` row: `ADD dex_count :one`. Emits the `first_find` reward.
   - `ConditionalCheckFailedException` → `is_first_find = False`. No `MEMBER#` update. Emits the `repeat_find` reward.

   `is_first_find` is written to `ctx.results["dex"].state` so downstream handlers read it without issuing their own Dex query.

`rarest_tier` on the `MEMBER#` row — originally bundled with the `dex_count` update in `docs/data-model.md` — moves to `RarityHandler`, which is the handler that actually knows the tier for this observation. Handled as a conditional `UpdateItem` ("set rarest_tier if the new tier outranks the existing one").

## Consequences

### Positive

- **First-find detection stays atomic.** The conditional put is still the only source of truth; no read-then-write race is introduced. Invariant #3 in `docs/architecture.md` is preserved.
- **Handler ownership is restored.** `DexHandler` owns Dex logic end-to-end — the write, the counter bump, the reward. `RarityHandler` owns rarity logic end-to-end, including the `rarest_tier` counter. Matches the dispatcher premise that features are strangers to each other.
- **Downstream handlers skip a DynamoDB read.** `ExpeditionHandler` and `RarityHandler` read `ctx.results["dex"].state["is_first_find"]` instead of querying the Dex themselves. Fewer round-trips inside the 300ms dispatcher budget.
- **Docs reconcile.** `docs/data-model.md` and `docs/dispatcher.md` are updated in the same PR as this ADR to match the two-step pattern.

### Negative

- **Each first-find costs one extra `UpdateItem`.** The submission transaction is 2 ops; on first-find there's an additional `PutItem` (conditional) plus an `UpdateItem` on `MEMBER#` for `dex_count`, and later another `UpdateItem` from `RarityHandler` for `rarest_tier`. On repeat-find, only the conditional `PutItem` (which fails cheaply). At 10k observations/day with ~30% first-find rate this is a rounding error on the bill.
- **Partial failure window exists between the submission transaction and the handler writes.** If the Lambda crashes after the transaction commits but before `DexHandler` runs, the kid has an `OBS#` row and an incremented `observation_count` but no `DEX#` row and no celebration. The dispatcher's per-handler exception isolation does not cover this case — the crash is above the dispatcher. Mitigation: a replay job (see follow-ups) scans recent `OBS#` rows missing their Dex counterpart and re-runs the dispatcher for them. Aligned with the documented invariant that "a failed handler never fails submission, but may require replay."
- **Counter updates are no longer in one atomic write.** `observation_count`, `dex_count`, and `rarest_tier` land on the `MEMBER#` row in up to three separate `UpdateItem` calls. DynamoDB atomic counters are commutative (`ADD`) so there's no lost-update hazard, but a reader hitting the `MEMBER#` row mid-dispatch may see an intermediate state. The leaderboard is only read from the UI and always lags the observation by whatever the network RTT is, so this is fine in practice — but it's a documented semantic shift from "one transaction writes everything" to "counters converge quickly."

### Neutral

- **Transaction cost is 2x write units instead of the original 3x plan.** Strictly cheaper, because fewer operations cross the transaction boundary.
- **Idempotency story is unchanged.** Re-running `DexHandler` against the same observation is safe: the conditional put fails on the second attempt, the counter update does not happen. This is the snapshot-test scenario #10 that was already in the Phase 1 ship gate.

## Alternatives considered

### Keep the three-op transaction; surface the condition result via `TransactionCanceledException`

**Rejected.** Technically possible: attempt the three-op transaction with the `DEX#` conditional, catch `TransactionCanceledException`, inspect `CancellationReasons`, and on conditional failure re-issue a two-op transaction without the `dex_count` bump and without the `DEX#` put. It works, but: (a) it's two transactions on every repeat-find — net more writes, not fewer; (b) the control flow bakes Dex-aware logic into the submission endpoint, violating the dispatcher premise; (c) error inspection on `TransactionCanceledException.CancellationReasons` is awkward and version-dependent across boto3 versions.

### Pre-compute `is_first_find` with a `GetItem` before the transaction

**Rejected.** Classic read-then-write race: two concurrent submissions of the same species both see "no Dex row yet," both try to bump `dex_count`, one silently double-counts. `docs/architecture.md` invariant #3 and ADR 0001 explicitly chose conditional writes to avoid this antipattern.

### Put `DEX#` inside the transaction with unconditional `Put` semantics (idempotent upsert)

**Rejected.** Loses first-find detection entirely. No way to distinguish a first write from a repeat without the conditional, and without first-find the reward system collapses.

## Follow-ups

- **Same-PR docs updates** (done alongside this ADR, not deferred):
  - `docs/data-model.md` "Transactional writes" section replaced with the two-op description plus a paragraph explaining the handler-owned `DEX#` write.
  - `docs/dispatcher.md` `DexHandler` handler description updated to note it owns the `dex_count` counter update.
  - `docs/dispatcher.md` `RarityHandler` description updated to note it owns the `rarest_tier` counter update.
  - `docs/dispatcher.md` `HANDLERS` ordering comment updated: `RarityHandler` is no longer "independent" — it writes to `MEMBER#` and depends on running after any other handler that also touches it.
- **Replay job** — a script in `scripts/replay_missed_dispatch.py` that queries recent `OBS#` rows, checks for matching `DEX#` existence, and re-invokes the dispatcher for any observation whose dispatch output is missing. Target Phase 1 Week 12.
- **Alarm** — CloudWatch alarm on a metric "observations older than 1 hour without a matching Dex row." Scope into Phase 1 Week 12 alongside the replay job.
- **Snapshot test scenario #11** — "Lambda crashes after submission transaction commits but before `DexHandler` runs; replay recovers." Added to the dispatcher test grid in `docs/dispatcher.md`. Test implementation in Phase 1 Week 8.
