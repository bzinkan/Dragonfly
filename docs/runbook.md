# Dragonfly Runbook

Operational playbook for Dragonfly. Each section describes a specific alert or incident class, the signal that triggers it, and the step-by-step response. Nothing here assumes a second operator — every procedure must be runnable by one tired person at 2am.

Related reading: `architecture.md` (what the system looks like when it's healthy), the ADRs (why the system looks the way it does).

---

## DNS — `dragonfly-app.net` is on Cloud DNS

**Authority.** As of 2026-05-05, the zone for `dragonfly-app.net` lives in Cloud DNS under managed zone `dragonfly-app-zone` in project `dragonflyapp-495423`. Squarespace is the **registrar** only — it no longer serves DNS. The four authoritative nameservers are `ns-cloud-a1` through `ns-cloud-a4.googledomains.com.`

**Records under management.**

| Name | Type | Value | TTL | Purpose |
|---|---|---|---|---|
| `dragonfly-app.net.` | A (×4) | Squarespace web hosting IPs | 14400 | Landing/marketing site (still hosted at Squarespace) |
| `dragonfly-app.net.` | MX | `1 smtp.google.com.` | 3600 | Workspace mail |
| `dragonfly-app.net.` | TXT | `v=spf1 include:_spf.google.com ~all` | 3600 | SPF |
| `google._domainkey.dragonfly-app.net.` | TXT | `v=DKIM1; k=rsa; p=...` (410 chars, split) | 3600 | DKIM |
| `www.dragonfly-app.net.` | CNAME | `ext-sq.squarespace.com.` | 14400 | www → Squarespace |
| `api.dragonfly-app.net.` | CNAME | `ghs.googlehosted.com.` | 300 | Cloud Run mapping for `dragonfly-api` |

**Adding a new record.** Always use a transaction so partial failures don't leave the zone half-changed.

```bash
gcloud dns record-sets transaction start --zone=dragonfly-app-zone
gcloud dns record-sets transaction add "<value>" \
  --name=<host>.dragonfly-app.net. --type=<TYPE> --ttl=<ttl> \
  --zone=dragonfly-app-zone
gcloud dns record-sets transaction execute --zone=dragonfly-app-zone
```

For TXT values longer than 255 chars (DKIM, long site-verification tokens), split into multiple quoted strings within one rrdata: `'"first 255 chars" "remaining chars"'`. Resolvers concatenate per RFC 6376.

**Rollback to Squarespace DNS.** If something goes wrong: at the Squarespace registrar dashboard, restore the old nameservers (`nsc1–4.squarespacedns.com`). The Squarespace zone records were not deleted on migration day; cutover is reversible at the registrar level alone, no Cloud DNS changes needed.

**Verifying mail continuity post-cutover.**

```bash
# After NS swap, confirm MX still resolves to Workspace from a fresh resolver:
nslookup -type=MX dragonfly-app.net 8.8.8.8
# Or against any Cloud DNS NS directly:
nslookup -type=MX dragonfly-app.net ns-cloud-a1.googledomains.com
```

Expected: `dragonfly-app.net mail exchanger = 1 smtp.google.com`. If this drifts, mail to `*@dragonfly-app.net` will silently bounce — investigate immediately.

---

## Smoke-testing `/health` in dev

**Why this is here.** The `dragonfly-app.net` Workspace org enforces `iam.allowedPolicyMemberDomains`, which blocks `--allow-unauthenticated` on Cloud Run services. Every endpoint — including `/health` — requires a valid identity token. The org policy is intentionally left intact (per ADR 0005 deploy notes) because Firebase Auth (Week 3) replaces this with the proper auth model.

**Command.**

```bash
curl -H "Authorization: Bearer $(gcloud auth print-identity-token)" https://api.dragonfly-app.net/health
```

Expected response:

```json
{"status":"ok","env":"dev","version":"0.1.0"}
```

If you get HTTP 403 with `Your client does not have permission`: your gcloud identity isn't authorized to invoke the service. Either authenticate as `brian@dragonfly-app.net` (the Cloud Run service grants `run.invoker` on `dragonflyapp.net`-domain principals only) or impersonate a service account that has the role.

**When this changes.** Once Firebase Auth lands in Week 3, `/health` should be moved to a public allow-list (org policy exception or IAP exclusion) so external monitoring can hit it without a Google identity. All other endpoints will accept Firebase ID tokens issued to parent/teacher/kid accounts.

---

## iNat submit DLQ has messages

**Signal.** CloudWatch alarm: `iNat submit DLQ depth > 0` for 5 minutes.

**What it means.** An observation was submitted by a kid, the submission transaction committed, the dispatcher ran and the kid saw their celebration — but the async push to iNaturalist failed enough times that SQS redrove the message to the dead-letter queue. The `OBS#` row exists in our database and the kid believes they contributed to science; iNat has not actually received anything.

**Impact.** Data loss relative to our promise to users. Not a user-visible outage.

**Response.**

1. Check the DLQ size and the age of the oldest message:

   ```bash
   aws sqs get-queue-attributes \
     --queue-url $INAT_SUBMIT_DLQ_URL \
     --attribute-names ApproximateNumberOfMessages ApproximateAgeOfOldestMessage
   ```

2. Sample a few messages to classify the failure. The most common causes, in order: (a) iNat is down or returning 5xx — look at status.inaturalist.org, (b) our project account's rate limit or auth token expired, (c) the observation's photo URL returned 4xx when iNat tried to fetch it (S3 presigned URL expired, quarantined photo), (d) a schema mismatch because iNat changed their API.

3. If iNat is down: wait. The DLQ retention is 14 days; we have time. Open an incident only if iNat is down for more than 24 hours or if the DLQ is growing faster than 100 messages/hour (indicates the retry policy is pushing things through too fast).

4. If our auth is expired: rotate the iNat project account credentials in SSM Parameter Store (`/dragonfly/{env}/inat/access_token`), then redrive:

   ```bash
   aws sqs start-message-move-task \
     --source-arn $INAT_SUBMIT_DLQ_ARN \
     --destination-arn $INAT_SUBMIT_MAIN_ARN
   ```

5. If the photo is missing or quarantined: these observations need to be abandoned at the iNat level. Leave the message in the DLQ for now; a follow-up script (Phase 1 Week 12) will annotate the `OBS#` row with `inat_abandoned: true, inat_abandon_reason: "photo_quarantined"` and delete the DLQ message.

6. If the iNat API changed shape: roll back the `inat_submit` Lambda to the last known-good version (CDK + CloudFormation stack update), then patch on main and redeploy. Redrive after.

**Close.** Alarm clears when the DLQ is empty. File a note in `docs/runbook_log.md` with the root cause; the next occurrence of the same root cause gets a real fix, not a redrive.

---

## Quarantine photo + `OBS#` row lifecycle

**Signal.** Not currently alarmed — this section is a proactive runbook for a known gap (see ADR 0004 follow-ups).

**What it means.** Photos flagged by Rekognition are moved to the `quarantine/` S3 prefix and a `REVIEW#` row is written to the group partition. The S3 lifecycle rule deletes quarantined objects after 30 days. The `OBS#` row that references the photo does not have an automatic cleanup, so after 30 days we have dangling references.

**Response on teacher review.**

1. Teacher reviews in the app; marks the `REVIEW#` row as `approved` or `rejected`.
2. On `approved`: move the photo from `quarantine/` to `observations/`, update the `OBS#` row's `photo_key`, trigger a fresh iNat submit via SQS (the original was suppressed).
3. On `rejected`: delete the `OBS#` row AND the `DEX#` row that points at its `first_obs_id` (if any), AND decrement the `dex_count` / `observation_count` counters on the `MEMBER#` row. Same-group kid never sees the observation, and the Dex is consistent.

**Response when a `REVIEW#` row ages past 30 days without a teacher decision.**

1. The S3 photo is already gone by now. The `OBS#` row points nowhere.
2. Nightly sweep (implemented in `scripts/sweep_stale_reviews.py`, Phase 1 Week 12) finds `REVIEW#` rows older than 30 days with status `pending`, auto-rejects them, and runs the rejection path above.
3. Teacher gets a digest email: "N observations auto-rejected due to no review within 30 days." Teachers are incentivized to review promptly; auto-rejection is the failsafe.

---

## Rarity refresh job stalled

**Signal.** CloudWatch alarm: `rarity job duration > 12 minutes` OR `rarity job has not completed for 48 hours`.

**What it means.** The nightly rarity refresh Lambda either ran long (approaching its 15-minute Lambda limit) or hasn't checkpointed in two runs. Rarity data for new observations is going stale; `RarityHandler` will emit less accurate tier rewards, but no user-visible failure.

**Response.**

1. Check `JOB#rarity/STATE` for the last-known cursor:

   ```bash
   aws dynamodb get-item \
     --table-name Dragonfly-$DRAGONFLY_ENV \
     --key '{"PK":{"S":"JOB#rarity"},"SK":{"S":"STATE"}}'
   ```

2. Read recent Lambda logs: look for `rarity_refresh.resumed from=<cursor>` lines to confirm self-continuation is working.

3. If the cursor is advancing but slowly: iNat is likely rate-limiting us. Don't parallelize — that makes it worse. Increase the Lambda timeout's follow-up cron gap (currently 03:00 UTC; add a 04:00 UTC continuation) and let it catch up organically.

4. If the cursor is stuck: likely a specific region's iNat query is erroring. Manually advance the cursor past the failing region, file a bug for investigation, re-run.

5. If the job has never completed: check that EventBridge is firing the cron. A failed CDK deploy can leave the rule disabled.

---

## Restore from point-in-time recovery

**Signal.** Data corruption, accidental mass delete, bad migration script.

**What it means.** We need to restore DynamoDB from PITR. Available in `staging` and `prod`; **disabled in `dev`** by `data_stack.py` to keep costs low.

**Response.**

1. Decide the restore target time. Err on the earliest clearly-good timestamp — we can always replay forward, but we can't un-overwrite.

2. Restore to a new table (never in-place):

   ```bash
   aws dynamodb restore-table-to-point-in-time \
     --source-table-name Dragonfly-prod \
     --target-table-name Dragonfly-prod-restore-$(date +%s) \
     --restore-date-time 2026-04-22T08:00:00Z
   ```

3. Point the Lambda at the restore table via a CDK diff + deploy that updates `DRAGONFLY_TABLE_NAME`. Validate reads before flipping writes.

4. Once validated: rename. DynamoDB doesn't support rename — instead, update the original table's name in CDK to a `-retired` suffix and the restore to the canonical name, deploy, then drop the retired table after 7 days of confidence.

5. Writes that happened after the restore point are lost. Pull the CloudWatch Logs range for the missing window and replay any `OBS#` rows manually via `scripts/replay_missed_dispatch.py`.

---

## Per-request LLM call detected from API Lambda

**Signal.** CloudWatch alarm: `LLMCallsFromApiLambda > 0` (metric filter on Anthropic or Gemini API calls in the API Lambda logs).

**What it means.** ADR 0002 forbids LLM calls on the kid hot path. Any occurrence here is a violation of that ADR — someone (or some dependency update) has introduced a runtime LLM call.

**Response.**

1. Identify the code path. Search the logs for the log line that captured the LLM call; the stack trace will name the calling module.

2. Revert immediately. This is a hotfix, not a discussion. The Lambda is serving kids; every minute the code is live, an LLM is being prompted with kid-proximal context.

3. After the revert, file an ADR variance: either ADR 0002 was wrong (unlikely — re-read it first), or the new code should have been an author-time script (likely), or we genuinely do want the exception and need to update ADR 0002 with explicit carve-out language.

4. Do not rely on the alarm alone in the future. Add a unit test at the API Lambda boundary that mocks `httpx.AsyncClient` and fails the build if any LLM host is ever called.

---

## Hot group partition

**Signal.** CloudWatch alarm on `ConsumedWriteCapacityUnits` per-GSI or `ThrottledRequests` on the main table partition for a specific `GROUP#<id>` hot key. Typically first appears as user-visible slowness in leaderboard refreshes for one group.

**What it means.** ADR 0001 anticipated this: a single group with many concurrent observations can push the `GROUP#<id>` partition past DynamoDB's per-partition throughput limits. Fine at our scale; real risk above 5k DAU or a viral school cohort.

**Response.**

1. Confirm it's partition heat, not a global table scaling issue. CloudWatch Insights query:

   ```
   fields @timestamp, @message
   | filter @message like /ThrottledRequest/
   | stats count() by bin(5m)
   ```

2. Short term: identify the affected `GROUP#<id>`. Use on-demand's elastic capacity to absorb the spike — no action needed if the throttling is brief and clears.

3. Medium term (if sustained): shard the group key.

   - Update `db/keys.py` to write `GROUP#<id>#<shard>` where `<shard>` is `hash(user_id) % N_SHARDS`.
   - Leaderboard reads become N parallel `Query` calls, results merged in Lambda memory. Fine at N ≤ 8.
   - Deploy in stages: writes dual-write to old and new keys for one week, reads flip to new keys, old keys backfilled via a one-time script, old keys deleted.

4. `N_SHARDS` starts at 4. Tune based on observed load; ADR 0001 allows up to 16 without revisiting the ADR.

---

## When this runbook is wrong

Running into something that isn't covered here, or discovering that a covered procedure doesn't work as written: open `docs/runbook.md` and fix it before you close the incident. A runbook that accumulates known bugs becomes a runbook that gets ignored. File updates are part of the incident, not follow-up.
