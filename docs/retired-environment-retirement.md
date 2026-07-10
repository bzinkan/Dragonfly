# Retired Environment Retirement

The Hinterland Azure environment is the only runtime. This runbook governs
retirement of the former environment after the rebranded API, websites, and
fresh mobile package have passed acceptance.

## Acceptance Gate

Record a release ticket containing all of the following before retirement:

1. `health`, `ready`, and the Hinterland kid JWKS endpoint return 200.
2. Azure API, Static Web Apps, and content-sync deployment checks are green.
3. Adult sign-in, kid handoff, photo upload and identification, Field Journal,
   and Expedition pass from the fresh mobile package.
4. The former environment inventory is attached to the ticket, including
   database, blob storage, DNS, app registrations, mobile artifacts, and
   deployment credentials.

## Fresh Mobile Package Cutover

`app.thehinterlandguide` is a fresh Android sandbox. SQLite and SecureStore
from an older package cannot and must not be copied into it.

1. Keep each old app installed while an adult inventories its owner-scoped
   Observation queue.
2. For every queued row, either obtain the canonical server Observation through
   normal reconciliation or have the adult explicitly discard it. Record only
   counts and outcomes—never local paths, photos, child text, or coordinates.
3. Do not expose an old owner's queue while testing a new account.
4. Once the queue is empty/reconciled, retire the old install and perform the
   normal fresh kid handoff in `app.thehinterlandguide`.
5. When no old package was ever installed, record `zero old installs` in the
   release ticket. A skipped or blank row does not satisfy this gate.

## Backup And Verification

1. Export the former database and blobs to an encrypted offline archive.
2. Record archive checksums, the encryption-key custody location, and the
   export manifest outside this repository.
3. Restore the archive into an isolated verification target and record the
   successful integrity check. Do not import that data into Hinterland.
4. Set a retention deadline exactly 30 days after verification. Access is
   restricted to the designated operator during that window.

## Retirement

After the retention deadline, securely delete the verified offline archive and
its temporary restore target. Then remove the former DNS and deployments, app
registrations, cloud resources, Play artifacts, EAS project association, and
deployment secrets. Record completion in the release ticket.
