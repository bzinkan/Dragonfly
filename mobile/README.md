# Dragonfly mobile

Expo (React Native) app for Dragonfly. iOS, Android, and a thin web build for the
parent-consent / teacher dashboard surface (per `docs/mobile.md`).

This is the Phase 5 scaffold: it boots, shows a Home tab that hits the deployed
`/health` endpoint, and stubs the other Phase 1 tabs (Observe / Dex /
Expeditions / Settings). Real screens land in Phase 6+.

## Quick start

```powershell
cd mobile
npm install
npm run start         # opens the Expo dev server; scan QR with Expo Go
npm run web           # browser preview at http://localhost:8081
```

Defaults to `APP_ENV=development`, which points the API base URL at
`https://api.dragonfly-app.net`. Other envs:

```powershell
$env:APP_ENV="preview";    npm run start
$env:APP_ENV="production"; npm run start
```

The active env, API URL, and update channel are visible on the Settings tab.

## Layout

```
mobile/
  app.config.ts        # env-switched Expo config (replaces app.json)
  eas.json             # development / preview / production build profiles
  app/                 # Expo Router file-based routes
    (tabs)/            # bottom tab nav: Home, Observe, Dex, Expeditions, Settings
  src/
    api/health.ts      # GET /health typed wrapper
    config/env.ts      # typed read of expoConfig.extra
  components/          # shared UI bits
```

`app/` is the Expo Router roots — anything in there becomes a route. `src/`
holds non-route code (API clients, config, future state stores).

## Environment switching

`APP_ENV` is read at build/start time by `app.config.ts` and baked into
`Constants.expoConfig.extra`. `src/config/env.ts` is the single typed read site
— do not call `Constants.expoConfig.extra` from screens directly.

| APP_ENV       | API base URL                          | Bundle ID                  | Update channel |
| ------------- | ------------------------------------- | -------------------------- | -------------- |
| `development` | `https://api.dragonfly-app.net`       | `com.dragonfly.app.dev`    | `development`  |
| `preview`     | `https://api.staging.dragonfly-app.net` (TBD) | `com.dragonfly.app.staging` | `preview`      |
| `production`  | `https://api.dragonfly-app.net` (TBD prod URL) | `com.dragonfly.app`        | `production`   |

Staging and production API URLs are placeholders until those environments
exist (per `infra-gcp/README.md`).

## What's NOT in this scaffold (yet)

Per `docs/mobile.md` the full stack adds Nativewind, Zustand, TanStack Query,
Sentry, expo-camera/-location/-image-manipulator/-sqlite, the offline queue,
the celebration sequence, and EAS Update. Each lands with the phase that
needs it — see `AGENTS.md` Phases 6–11. This scaffold is intentionally bare:
just what proves the app boots, switches envs correctly, and reaches the
deployed API.
