# Risk 0007: Google Play Families policy + precise-location permission

- **Status:** Mitigated for Play Internal; keep open until device verification
- **Date filed:** 2026-06-03
- **Updated:** 2026-06-04
- **Chosen option:** Option B, coarse/foreground location for `play-internal`
- **Owner:** Brian

## Decision

The `play-internal` Android build must not request
`android.permission.ACCESS_FINE_LOCATION`. It explicitly requests
`android.permission.ACCESS_COARSE_LOCATION` and blocks fine location in
`mobile/app.config.ts`.

This preserves location semantics for observations while reducing the child
privacy/compliance risk before any Google Play Internal Testing upload.

## Code State

- `APP_ENV=play-internal` uses package `com.dragonfly.app` and display name
  `Dragonfly Internal`.
- `android.blockedPermissions` includes
  `android.permission.ACCESS_FINE_LOCATION`.
- `android.permissions` includes
  `android.permission.ACCESS_COARSE_LOCATION`.
- CI runs `APP_ENV=play-internal npm run config:play-internal` to verify the
  public Expo config.

## Remaining Verification

- [ ] Run an EAS `play-internal` AAB build.
- [ ] Inspect/confirm the generated Android manifest has no fine-location
      permission.
- [ ] Install on a physical Android device from Internal Testing.
- [ ] Confirm the runtime location prompt matches coarse/approximate behavior.
- [ ] Record the chosen option and device result in the private pilot journal.

## Rule

Do not promote a build past Internal Testing until this verification is complete
and the current Google Play review requirements are rechecked against official
store docs.
