# Risk 0003: Dispatcher snapshot scenarios + p95 budget not fully validated

- **Status:** Open
- **Date filed:** 2026-05-10
- **Source:** Phase 9 exit criteria ("All dispatcher snapshot scenarios pass" + "Dispatcher p95 meets the documented budget")
- **Owner:** Brian (needs DB-backed test harness + a real-traffic baseline before any tuning)

## What we have

PRs #49-52 shipped the dispatcher core, DexHandler, RarityHandler, and an ExpeditionHandler stub, with `dispatch()` wired into `POST /v1/observations`. Mock-based snapshot tests cover scenarios 1, 2, 3, 5, and 9 from the `docs/dispatcher.md` table (full state-of-the-world contract: given DB state, return ordered `[Reward, ...]`).

## What's not validated yet

### Snapshot scenarios

| # | Scenario | Why deferred |
|---|---|---|
| 4 | First find, rare species, region with `low_data` (uses parent geohash-3) | RarityHandler doesn't implement the geohash-3 fallback yet. Tracked in `app/dispatcher/handlers/rarity.py` docstring. ~2 hours of work once we have a `low_data` cell to test against. |
| 6 | Observation completes an expedition step | `ExpeditionHandler` is a stub returning `[]`. Full impl needs Phase 10 (Content + Expeditions): expedition Pydantic schema, `content/expeditions/` source tree, validate + sync scripts, matcher registry. |
| 7 | Observation completes the final step of an expedition | Same blocker as #6. |
| 8 | One observation advances steps in two expeditions simultaneously | Same blocker as #6. |
| 10 | Same observation submitted twice (idempotency) | Handler-level invariants (Dex's `INSERT ... ON CONFLICT`, Rarity's idempotent UPSERT) are exercised by the per-handler unit tests. The end-to-end-on-real-DB version of this test needs the Phase 11 test harness. |
| 11 | API service crashes after submission tx but before dispatch; replay recovers | This is the ADR 0004 replay path -- the spec exists but the replay job itself isn't built (it's a Phase 11 dogfood-period operational concern). |

### p95 budget

`docs/dispatcher.md` specifies handlers MUST be <100ms p95 individually with the full dispatcher under 300ms p95. Verifying this needs:

- Real traffic against a real Postgres (Cloud SQL `dragonfly-postgres-dev`).
- A latency-collection point. Cloud Run + Cloud Logging captures request latency, but we don't yet break out the dispatcher portion separately.
- ~50+ observations to make a p95 calculation meaningful.

We have **zero** real observations as of this risk filing. Measuring p95 today would be nonsense.

## Mitigation in the meantime

The handler contracts and dispatcher core are unit-tested for correctness against mocked DB state. Per `docs/dispatcher.md` the dispatcher's exception isolation is structurally guaranteed -- a handler that exceeds its budget would still leave the kid's submission unaffected (the dispatcher returns whatever rewards completed in time). There's no failure mode where slow handlers break submission.

The deferred snapshot scenarios all share one of two unblock paths:

- **Phase 10**: ExpeditionHandler full impl unblocks 6, 7, 8.
- **Phase 11**: Real-DB test harness unblocks 4, 10, 11.

p95 measurement is a Phase 11 dogfood-window task: once a dozen kids have submitted real observations on dev, we can pull the request-latency distribution from Cloud Logging and check.

## Production unblock checklist

Order matters loosely (Phase 10 before Phase 11, then dogfood + measurement).

- [ ] Phase 10 builds the expedition matcher registry + content tree
- [ ] Implement `ExpeditionHandler.handle` against the real matcher; add scenarios 6, 7, 8 to `tests/test_dispatcher_snapshots.py`
- [ ] Implement RarityHandler geohash-3 fallback for `low_data` cells; add scenario 4
- [ ] Phase 11 builds the real-Postgres test harness (`run_dispatch` per `docs/dispatcher.md` "Testing")
- [ ] Move scenarios 10 + 11 to that harness; add a fresh `tests/test_dispatcher_snapshots_real_db.py`
- [ ] Add a structured log line `dispatcher.duration_ms` per dispatch run (already partially logged via `dispatcher.complete` -- add explicit ms)
- [ ] Cloud Monitoring dashboard reads `dispatcher.duration_ms` 95th percentile; alarm when >300ms sustained
- [ ] Dogfood window: 12+ kids submit ~50 real observations; confirm p95 dispatcher latency under 300ms
- [ ] Close this risk with the measured p95
