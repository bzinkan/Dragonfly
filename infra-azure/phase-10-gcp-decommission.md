# Phase 10 -- GCP decommission record

Date: 2026-06-03. This is a written record of the GCP-side decisions that
land alongside the migration to Azure. Sister document to ADR 0010.

## Scope cuts vs the ADR

ADR 0010 Phase 10 originally listed: disable Cloud Run, snapshot + delete
Cloud SQL, delete GCS bucket, disable Firebase Hosting, delete Cloud DNS
zone. The decommission that actually shipped is narrower and pragmatic.

| ADR action | What actually shipped | Why |
|---|---|---|
| Disable Cloud Run | **Deleted** `dragonfly-api` service | Image still in Artifact Registry; trivially recreatable. |
| Snapshot + delete Cloud SQL | **Stopped** `dragonfly-postgres-dev` (activationPolicy=NEVER) | Stop preserves data + automated backups, zero compute cost (~$15-25/mo saved). Reversible with one `gcloud sql instances patch --activation-policy=ALWAYS`. Delete is irreversible; not worth the risk for $0 additional savings. |
| Delete GCS bucket | **Kept** `dragonfly-photos-dev-dragonflyapp-495423` as-is | Empty/near-empty bucket; storage cost is ~$0. No reason to incur the migration cost of azcopy + lifecycle juggling for a beta bucket. Phase 11 (if ever) deletes it after a 30-day retention window. |
| Disable Firebase Hosting parents site | **Kept** `dragonfly-parents-dev` live | Apex + www of the public domain still need a host; Azure SWA apex requires Azure DNS specifically and we kept Cloud DNS as authoritative. Firebase Hosting Free tier is $0. See "Persistent Firebase footprint" below. |
| Delete Firebase Auth tenant | **Kept** the project | Phase 7 MSAL bundler issue (msal-common exports map) means the mobile app still uses Firebase Auth for parent sign-in on every platform. Firebase Auth Free tier is $0. Phase 11 candidate. |
| Delete Cloud DNS zone | **Kept** `dragonfly-app-zone` as authoritative | Holds the records for the apex + www (Firebase Hosting) + api + parents (Azure). Cost ~$1/mo. Moving to Azure DNS requires a registrar repoint + apex + www re-cert and isn't worth the lift for the beta. |

## What actually changed

Deleted in GCP:
- `gcloud run services delete dragonfly-api --region=us-central1` -- the Cloud Run service is gone.

Stopped in GCP:
- `gcloud sql instances patch dragonfly-postgres-dev --activation-policy=NEVER` -- the instance shows STOPPED, no compute charge.

Kept in GCP (intentionally):
- Cloud SQL instance shape + data + backups (for restart)
- GCS bucket (photos)
- Firebase Hosting sites: `dragonfly-landing-dev` (apex + www), `dragonfly-parents-dev` (now unused, but kept as standby)
- Firebase Auth tenant `dragonflyapp-495423`
- Cloud DNS zone `dragonfly-app-zone`
- Artifact Registry images

## Persistent Firebase footprint (apex + www)

The apex `dragonfly-app.net` and `www.dragonfly-app.net` are still served by
Firebase Hosting site `dragonfly-landing-dev`. Azure Static Web Apps
supports custom apex domains only when Azure DNS is the authoritative
nameserver; we kept Cloud DNS because:

- It's $1/mo;
- All records (api + parents on Azure, apex + www + email on Firebase / GCP)
  are already there;
- Migrating the zone would require a registrar-side NS change + cert
  reissue on every record, for marginal benefit.

If/when Azure DNS migration becomes worthwhile, the path is:
1. Recreate the zone in Azure DNS, import all records.
2. Update registrar NS records to point at Azure DNS nameservers.
3. Claim `dragonfly-app.net` + `www.dragonfly-app.net` as apex/subdomain
   on `dragonfly-landing-swa`.
4. Delete Firebase Hosting sites.

## Cost delta

| Line item | Before | After |
|---|---|---|
| GCP Cloud Run (idle) | ~$0 | $0 (deleted) |
| GCP Cloud SQL B1ms | ~$15-25/mo | $0 (stopped) |
| GCP Cloud Storage (~10GB) | ~$0.20/mo | $0.20/mo (kept) |
| GCP Cloud DNS | ~$1/mo | $1/mo (kept) |
| GCP Firebase Hosting / Auth | $0 (free) | $0 (kept) |
| **GCP total** | **~$17-27/mo** | **~$1.20/mo** |
| Azure Postgres B1ms | $0 | ~$15-25/mo |
| Azure Container Apps (min=0) | $0 | $0-25/mo |
| Azure Storage / KV / ACR / SWA | $0 | ~$6/mo |
| Azure Content Safety F0 | $0 | $0 (free 5k/mo) |
| **Azure total** | **$0** | **~$25-55/mo** |

Net new spend ~$10-30/mo above the previous GCP-only baseline. $1000 credit
covers ~25-40 months at this profile. Well within bounds.

## Reversal procedure (if anything in Azure proves unworkable)

1. Restart Cloud SQL: `gcloud sql instances patch dragonfly-postgres-dev --activation-policy=ALWAYS`.
2. Recreate Cloud Run from the artifact-registry image: `gcloud run deploy dragonfly-api --image us-central1-docker.pkg.dev/dragonflyapp-495423/dragonfly/dragonfly-api:latest`.
3. Repoint `api.dragonfly-app.net` CNAME from the Container Apps FQDN back to `ghs.googlehosted.com.`
4. Repoint `parents.dragonfly-app.net` CNAME from the SWA hostname back to Firebase Hosting (199.36.158.100 A record).
5. Container App env var `DRAGONFLY_STORAGE_PROVIDER=gcs` + `DRAGONFLY_MODERATION_PROVIDER=cloud_vision_safesearch` flips the backend back to GCP services -- the auth path still uses Entra, but the rest of the backend works against the GCP datastore.

The migration is rollback-friendly through Phase 11 (Firebase Auth removal).

## Phase 11 candidates

Phase 11 is "everything that can wait":

- Real MSAL hookup on the parents web bundle (parents currently sign in via Firebase Auth even on web).
- Sign-in.tsx UI rewrite (Microsoft-hosted redirect button on web; email/password form stays on native).
- Drop `firebase-admin` + `google-cloud-storage` + `firebase` from dependencies once MSAL is real.
- Delete Cloud SQL instance + GCS bucket after a 60-day soak.
- Migrate Cloud DNS -> Azure DNS + cut apex/www over to Static Web Apps.
- Delete the Firebase project entirely.
