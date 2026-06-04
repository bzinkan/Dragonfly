# Risk 0002: Azure async safety/science pipeline not wired for closed beta

- **Status:** Open
- **Date filed:** 2026-05-10
- **Updated:** 2026-06-04 for ADR 0010
- **Owner:** Brian
- **Source:** Phase 8 exit criteria and ADR 0010 Azure migration

## What We Have

The code surface exists:

- `AzureContentSafetyModerator` behind the `Moderator` protocol.
- `process_pending_photo()` for pending -> clean/quarantine lifecycle.
- Adult review queue endpoints and mobile review UI.
- iNat submitter code with idempotency by Dragonfly observation id.
- Admin jobs for rarity refresh, stale-review sweep, and dispatcher replay.

The W1 Android Internal Testing pilot may run with:

- `DRAGONFLY_MODERATION_PROVIDER=noop`
- no iNat OAuth token configured
- no public iNaturalist submission
- adult-supervised manual review of the one or few pilot observations

That W1 posture is intentional and does not close this risk.

## What Is Still Missing For Closed Beta

- Azure Blob/Event Grid or Service Bus trigger for `pending/` photo moderation.
- Azure internal caller auth model for `/internal/*` or direct worker execution.
- `DRAGONFLY_MODERATION_PROVIDER=azure_content_safety` configured from Key Vault.
- `observations.moderation_status` and `observations.moderation_labels` migration.
- Clean moderation path enqueues iNat submit work only after safety decision.
- iNat retry/DLQ/dead-letter visibility.
- Scheduled Azure jobs for rarity refresh, stale-review sweep, and dispatcher replay.
- Azure Monitor alerts/dashboards for API errors, moderation failures, iNat failures,
  queue/DLQ depth, dispatcher replay backlog, Postgres pressure, and budget.

## Closure Checklist

- [ ] Close Risk 0001: iNat project account/OAuth token and 50-photo benchmark.
- [ ] Choose Azure async primitive: Event Grid -> queue -> Container Apps job, or
      Service Bus queue directly from API/worker code.
- [ ] Implement internal auth for Azure callers or remove HTTP `/internal/*`
      exposure in favor of queue/job execution.
- [ ] Configure Azure AI Content Safety endpoint/key through Key Vault-backed
      Container App secrets.
- [ ] Add `observations.moderation_status` and `moderation_labels` migration and
      update the processor to write them.
- [ ] Wire clean moderation path to enqueue iNat submit.
- [ ] Wire retry/DLQ and alerting for iNat submit.
- [ ] Wire scheduled Azure jobs for rarity/sweep/replay.
- [ ] Verify clean path: real safe photo goes pending -> observations and remains
      reviewable by the family/group.
- [ ] Verify flagged path: known test image goes quarantine -> review queue and
      approve/reject works.
- [ ] Verify iNat path: clean approved observation appears in iNaturalist within
      the target window.

## Mitigation

The kid hot path is structurally safe while this risk is open: submission returns
after the observation write and dispatcher run. Moderation/iNat outages cannot
fail the kid's submit response.
