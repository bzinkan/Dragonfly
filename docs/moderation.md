# Photo Moderation

Every photo a kid uploads is screened before it's visible in the app or submitted to iNaturalist. The screening runs in S3, not in the API Lambda, so that the observation-submission hot path never blocks on Rekognition. This doc describes the pipeline, the design decisions it depends on, and the edges that need special handling.

Related reading: `architecture.md` (how moderation fits into the observation flow), `data-model.md` (the `REVIEW#` row schema and membership counters), `runbook.md` (incident response for quarantined photos).

## The pipeline at a glance

```
kid uploads photo
         │
         ▼                    presigned PUT from /v1/photos/presign
   s3://dragonfly-photos/pending/<obs_id>.jpg
         │
         │  s3:ObjectCreated:* event
         ▼
   ┌──────────────────────┐
   │ moderation Lambda    │
   │  ┌────────────────┐  │
   │  │ Rekognition    │  │ DetectModerationLabels
   │  │ /DetectMod...  │  │
   │  └────────────────┘  │
   └──────┬───────────────┘
          │
     ┌────┴──────┐
     │           │
  clean       flagged
     │           │
     ▼           ▼
 observations/ quarantine/
     │           │
     │           │  + write REVIEW# row
     │           │  + update OBS# row: quarantined=true
     │           │
     ▼           ▼
  inat_submit  teacher review queue
```

The moderation Lambda is the only component that writes to `observations/` or `quarantine/` — the API Lambda only writes to `pending/` (via presigned URL), never to either resolved prefix.

## Design decisions baked into this pipeline

**Moderation is synchronous with photo arrival, not with observation submission.** The kid uploads to `pending/`, then calls `POST /v1/observations`. Those two API calls are independent. The observation submission persists the `OBS#` row before moderation has finished. The kid sees their celebration immediately. This is the correct trade-off for the kid UX (they never wait on Rekognition) at the cost of a small window where the `OBS#` row exists but its photo isn't yet approved. The mobile app renders an observation-without-photo placeholder during that window.

**iNat submit waits for moderation.** We do not want to push an unmoderated photo to iNaturalist. The SQS message that `inat_submit` consumes is enqueued by the moderation Lambda on the clean path, not by the API Lambda at submission time. If moderation takes 2 seconds, iNat submit starts 2 seconds later. If moderation flags the photo, no SQS message is ever enqueued and iNat never sees it.

**Quarantine moves, it doesn't delete.** Flagged photos are copied to `quarantine/`, not deleted from S3. A human (teacher) review path can recover a false positive. The S3 lifecycle rule in `data_stack.py` deletes `quarantine/` objects after 30 days; by that point the review has either closed or been auto-rejected (see `runbook.md`).

**Failed Rekognition does not default-allow.** If Rekognition errors (throttle, service outage, transient 5xx), the photo stays in `pending/` and the Lambda retries with exponential backoff. The S3 lifecycle rule clears abandoned `pending/` objects after 24 hours; if moderation hasn't succeeded by then, the photo is gone and the observation's `photo_key` points nowhere — the mobile app treats this as a failed observation and surfaces it in the kid's "retry" list. This is intentional. Defaulting to "allow" on Rekognition failure means every Rekognition outage becomes a content-safety incident.

## Rekognition configuration

The moderation Lambda calls `rekognition:DetectModerationLabels` with:

- `MinConfidence` = 60 (moderate sensitivity — tune after gathering false-positive data)
- Label taxonomy v7 (`Explicit`, `Non-Explicit Nudity of Intimate parts and Kissing`, `Violence`, `Drugs & Tobacco`, `Alcohol`, `Rude Gestures`, `Hate Symbols`, `Gambling`). The full current taxonomy is at [https://docs.aws.amazon.com/rekognition/latest/dg/moderation.html](https://docs.aws.amazon.com/rekognition/latest/dg/moderation.html) — pinned to the taxonomy version in SSM so a taxonomy update doesn't silently change behavior.

Flag rule: **flag if any top-level parent label in the returned set has confidence ≥ threshold.** Subcategory-only matches (e.g. a low-confidence child label with no parent match) are allowed through. Threshold and label set are loaded from SSM Parameter Store at cold start:

- `/dragonfly/{env}/moderation/min_confidence` (default 60)
- `/dragonfly/{env}/moderation/flag_labels` (JSON array of top-level labels)

Changing the rule is a one-minute SSM update, no deploy required. That's deliberate — if we hit a real-world incident we need to tighten fast.

## What the moderation Lambda writes

On the clean path:

1. `CopyObject` from `pending/<obs_id>.jpg` to `observations/<obs_id>.jpg`.
2. `DeleteObject` on the `pending/` copy.
3. `UpdateItem` on the `OBS#` row: `SET photo_key = :new, moderation_status = "clean"`.
4. `SendMessage` to the iNat submit queue with the observation ID.

On the flag path:

1. `CopyObject` from `pending/<obs_id>.jpg` to `quarantine/<obs_id>.jpg`.
2. `DeleteObject` on the `pending/` copy.
3. `UpdateItem` on the `OBS#` row: `SET photo_key = :quarantine_key, moderation_status = "quarantined", moderation_labels = :labels` (labels stored for the teacher review UI to explain *why*).
4. `PutItem` for a `REVIEW#<ts>#<obsId>` row under the kid's group partition, with `GSI1PK = STATUS#pending` so admins can list across groups.
5. No iNat submit message.

On the error path (Rekognition 5xx, network fault):

1. No S3 moves.
2. Lambda raises; SQS (S3 event notifications are wrapped by an SQS queue at the CDK level — see `WorkersStack` when it lands) redelivers per its retry policy.
3. After N retries, message goes to a DLQ; `runbook.md` covers the response.
4. Lifecycle rule on `pending/` eventually cleans the stuck photo after 24 hours.

## Teacher review lifecycle

Quarantined photos are resolved by a teacher approving or rejecting the `REVIEW#` row from the mobile app (Week 11 in `roadmap.md`).

- **Approve.** Move photo from `quarantine/` to `observations/`, update `OBS#` row (`moderation_status = "approved_on_review"`, clear the quarantine flag), enqueue the delayed iNat submit, mark `REVIEW#` as `approved` with reviewer id and timestamp.
- **Reject.** Delete the `OBS#` row and its `DEX#` row (if any), decrement the user's `MEMBER#` counters, mark `REVIEW#` as `rejected`. The photo in `quarantine/` is left for the 30-day S3 lifecycle to sweep — we keep it briefly for audit and appeal.
- **Stale (no decision in 30 days).** The nightly sweep (`scripts/sweep_stale_reviews.py`) auto-rejects the review and runs the rejection path. See `runbook.md`.

Counters stay correct across all three paths because approve-on-review is an idempotent no-op on the counters (they were never bumped at submission, because on the flag path we don't bump) — wait, that's wrong. Let me be precise: `observation_count` *is* bumped at submission (by the submission transaction, before moderation has run). A flagged observation's `observation_count` stays bumped until the teacher reviews. On approve, nothing changes. On reject, the counter decrements. This is the correct semantic: the kid's observation count is what they've *submitted*, not what's been approved; the Dex (which is only written by `DexHandler` after moderation, per ADR 0004) is what's been *earned*.

Actually — `DexHandler` runs at submission time, not after moderation. So a first-find on a photo that later gets quarantined will have its `DEX#` row and `dex_count` bumped, and on reject those need to be un-done. This is handled by the rejection path: `DELETE` the `DEX#` row, `ADD dex_count :minus_one` on the `MEMBER#` row.

## What this doc doesn't cover

- **Text moderation** — if and when we add observation notes (kids can type a short caption). Plan is to use Rekognition's `DetectText` for photo content then send extracted text plus the kid's caption through a moderation model, but that's a Phase 3 discussion at earliest.
- **Appeals.** A rejected kid currently has no in-app path to contest. If appeals become a real need, the `REVIEW#` row gets a second status field and the workflow grows. Not for Phase 1.
- **Moderation metrics dashboard.** Counts by label, false-positive rate against teacher-overridden approvals, per-kid flag rate. These are observability improvements for post-beta.
