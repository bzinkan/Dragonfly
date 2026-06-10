# Sanctuary 3D asset pipeline

How 3D models get from CC0 packs (or Blockbench) into the app. Companion to
[ADR 0011](adr/0011-sanctuary-3d-rendering.md) and `docs/sanctuary.md` §10.

## Ground rules

- **CC0 only.** Every raw input is recorded in
  `scripts/sanctuary_assets/sources.json` (pack, URL, license, sha256).
  `validate.mjs` fails on any non-CC0 literal. Attribution UI conflicts with
  the no-external-links-for-kids invariant, so CC-BY models (e.g. the
  Poly-by-Google archive on Poly Pizza) are excluded.
- **Bundled, never fetched.** Processed GLBs are committed under
  `mobile/assets/sanctuary/models/` and ship in the binary. The scene renders
  fully offline (docs/sanctuary.md §10).
- **One palette.** Every material color is one of the 16 named slots in
  `palette/base.json`. Seasonal looks (`spring/summer/autumn/winter`) and the
  tier-0/silhouette look (`dormant`) are remaps of the same slot names — a
  runtime material-color write, not duplicate assets.
- **No Draco, no meshopt.** Both need WASM decoders and Hermes has no WASM.
  GLBs use `KHR_mesh_quantization` (no runtime decoder) + build-time
  simplification.
- **Budgets** (enforced by `validate.mjs` from `normalize.mjs`'s report):
  props ≤ 3k tris / 60 KB, animated creatures ≤ 8k tris / 500 KB, island base
  ≤ 10k tris / 1 MB, total committed payload ≤ 15 MB (20 MB hard ceiling).

## Workflow

```sh
cd scripts/sanctuary_assets
npm ci

# 1. Download a pack into .cache/ (git-ignored), add a sources.json entry
#    with the sha256 of the zip. Prefer the pack's glTF folder.

# 2. Describe the model in assets.json:
#    kind: "element" (carries an iconKey from content/sanctuary/*.json)
#       or "scenery" (carries zone + tierMin tier-dressing threshold)
#    paletteSlots: material name -> palette slot (the scriptable recolor —
#       e.g. the monarch is the butterfly mesh with wing material -> accent_warm)

# 3. Process raw -> committed GLB (+ report.json with size/tri stats):
node normalize.mjs --only <name>     # or no flag for everything

# 4. Regenerate the app manifest (mobile/src/sanctuary/assetManifest.gen.ts):
node build_manifest.mjs

# 5. Remove the model's icon key from placeholders.json, then gate:
node validate.mjs
```

CI (`.github/workflows/sanctuary-assets.yml`) re-runs steps 4–5 and fails on
manifest drift, coverage gaps, budget breaches, or license violations.

## File map

| Path | Role |
|---|---|
| `scripts/sanctuary_assets/sources.json` | Provenance ledger (CC0-enforced) |
| `scripts/sanctuary_assets/assets.json` | Authored mapping: model → zone/iconKey/tierMin/anchor/paletteSlots/animations |
| `scripts/sanctuary_assets/palette/*.json` | The 16-slot palette + seasonal/dormant remaps |
| `scripts/sanctuary_assets/layout/<zone>.json` | Named anchor points per zone (charismatic placement is deterministic 1:1) |
| `scripts/sanctuary_assets/normalize.mjs` | raw → dedup/join/weld → simplify → strip textures → palette snap → scale/origin normalize → animation whitelist → quantize → GLB |
| `scripts/sanctuary_assets/build_manifest.mjs` | assets.json → `assetManifest.gen.ts` (app) + `manifest.gen.json` (tooling) |
| `scripts/sanctuary_assets/validate.mjs` | CI gate: coverage, files, budgets, licenses, anchors |
| `scripts/sanctuary_assets/placeholders.json` | Icon keys awaiting models (scene renders a typed fallback). Goal: empty by asset milestone A6 |
| `scripts/sanctuary_assets/make_test_model.mjs` | Generates the M0 spike GLB (`models/dev/spike-tree.glb`) |
| `mobile/assets/sanctuary/models/` | Committed, processed GLBs only (raw packs stay in `.cache/`) |
| `mobile/src/sanctuary/assetManifest.gen.ts` | Generated — do not edit |

## Authored (Blockbench) models

Eight small models have no CC0 match and are hand-built in
[Blockbench](https://www.blockbench.net/) (free, low-poly box modeling, GLB
export): butterfly/monarch, hummingbird, perched songbird (reused as pigeon),
soaring bird (reused as hawk), snail, worm, glowing wisp, and the dragonfly
guide (the mascot — reuse the same model everywhere the guide appears).
Commit the `.bbmodel` source under `scripts/sanctuary_assets/sources_authored/`
and run them through `normalize.mjs` like any pack model.
