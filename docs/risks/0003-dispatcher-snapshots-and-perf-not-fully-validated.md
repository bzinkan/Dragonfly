# Risk 0003: Dispatcher real-DB snapshots and p95 still need proof

- **Status:** Open
- **Date filed:** 2026-05-10
- **Updated:** 2026-06-04
- **Owner:** Brian

## Current State

The original risk is partly stale:

- ExpeditionHandler is implemented.
- World/Sanctuary handler is implemented.
- Dispatcher replay job exists.
- RarityHandler now falls back from geohash-4 to parent geohash-3 when the
  child cell has no baseline.
- `dispatcher.complete` logs `duration_ms`.

Mock/unit coverage exists for dispatcher core, Dex, Rarity, Expedition, World,
and replay. The remaining gap is proof against a real Postgres database and a
real traffic latency distribution.

## Remaining Closure Checklist

- [x] Implement geohash-3 rarity fallback for low-data child cells.
- [x] Add `dispatcher.duration_ms`/`duration_ms` logging.
- [ ] Add or update snapshot coverage so scenarios 4, 6, 7, and 8 are visible
      from the dispatcher snapshot suite, not only per-handler tests.
- [ ] Add real-Postgres dispatcher harness for scenarios 10 and 11:
      idempotent resubmit and replay after crash.
- [ ] Run dogfood/pilot traffic until at least 50 observations exist.
- [ ] Query Azure Log Analytics for dispatcher p95 and confirm it is below
      300ms.
- [ ] Add an Azure Monitor chart/alert for sustained dispatcher p95 > 300ms.

## Mitigation

While this risk is open, dispatcher failure still does not fail observation
submission. The replay job can recover missing rewards where `dispatched_at`
stayed null.
