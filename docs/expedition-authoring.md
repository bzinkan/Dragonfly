# Expedition Authoring

Expeditions are the content that gives kids a reason to go outside. Each one is a short guided prompt ("find three things that fit these criteria") that the app runs against incoming observations, marking steps complete as matches come in and celebrating when the expedition finishes.

This doc is the reference for writing them: the file format, the match language, validation, and the sync pipeline that gets JSON from the repo to Postgres.

Related reading: `dispatcher.md` (how `ExpeditionHandler` interprets these files at observation time), `data-model.md` (how expedition progress is stored per-user).

## The file format

One JSON file per expedition, living in `content/expeditions/<tier>/<id>.json`. The filename stem must match the `id` field inside the file — the sync script enforces this.

```json
{
  "id": "backyard_starter",
  "title": "Start Where You Are",
  "subtitle": "Your first expedition",
  "tier": 1,
  "duration_minutes": 20,
  "environments": ["yard", "park", "street", "school", "other"],
  "theme": "warmup",
  "learning_goal": "Practice making a simple field set: one plant, one small animal, and one surprise organism.",
  "difficulty_label": "Warm-up",
  "preview_enabled": true,
  "unlock_hint": null,
  "intro": "Warm up with a simple field set: one plant, one insect, and one surprise organism from wherever you are.",
  "outro": "You just contributed real data to science. Welcome to Hinterland.",
  "prerequisites": [],
  "steps": [
    {
      "id": "any_plant",
      "description": "Find a plant — any plant",
      "match": { "kind": "iconic_taxon", "value": "Plantae" },
      "hint": "Grass, a weed in a sidewalk crack, a tree, a houseplant by a window — all count."
    },
    {
      "id": "any_insect",
      "description": "Find an insect or bug",
      "match": { "kind": "iconic_taxon", "value": "Insecta" },
      "hint": "Check under a leaf, near flowers, or on a wall."
    },
    {
      "id": "wildcard",
      "description": "Find one surprise organism",
      "match": { "kind": "any_organism" },
      "hint": "Bird, fungus, spider, snail — surprise us."
    }
  ]
}
```

### Top-level fields

| Field              | Type          | Notes                                                           |
|--------------------|---------------|-----------------------------------------------------------------|
| `id`               | string        | Snake_case, unique, stable forever (it keys expedition progress rows) |
| `title`            | string        | Shown large at the top of the expedition card                   |
| `subtitle`         | string        | Optional one-liner under the title                              |
| `tier`             | integer       | 1 = starter, 2 = unlocked after completing any tier 1, 3+ = themed |
| `duration_minutes` | integer       | Honest estimate — kids hate being told "quick" when it isn't    |
| `environments`     | list[string]  | Any of: `yard`, `park`, `street`, `school`, `other`. Filters which expeditions appear in the onboarding picker |
| `theme`            | string        | One of `warmup`, `food_web`, `pollinators`, `decomposers`, `trees`, `wetland`, `invasive`, `urban`, `seasonal`; drives placeholder card treatment |
| `learning_goal`    | string/null   | Short science outcome for cards and briefing screens            |
| `difficulty_label` | string/null   | Kid-facing scope label like `Warm-up`, `Starter ecology`, or `Needs a few finds` |
| `preview_enabled`  | boolean       | If true, locked expeditions can appear in the preview shelf before prerequisites are met |
| `unlock_hint`      | string/null   | Copy shown on locked preview cards, e.g. `Complete Tree Trio to unlock.` |
| `intro`            | string        | Shown when the kid opens the expedition                         |
| `outro`            | string        | Shown on completion, after the celebration sequence             |
| `prerequisites`    | list[object]  | See [Prerequisites](#prerequisites); empty for starters         |
| `steps`            | list[object]  | 2–5 steps is the sweet spot. More than 5 and kids drop off      |

### Step fields

| Field         | Type    | Notes                                                                          |
|---------------|---------|--------------------------------------------------------------------------------|
| `id`          | string  | Unique *within the expedition*; used in the progress row's completion map      |
| `description` | string  | One line, imperative voice ("Find…", "Spot…", "Look for…")                     |
| `match`       | object  | The match spec — see below                                                     |
| `hint`        | string  | Optional; shown if the kid taps the step. Concrete examples, not abstract help |
| `tag_prompt`  | object  | Optional closed-choice prompt for steps that need a kid-selected ecology tag   |

## The match language

Every step has a `match` block with a `kind` and kind-specific fields. When an observation comes in, `ExpeditionHandler` walks each of the user's active expeditions, finds the first incomplete step, and checks whether the observation satisfies that step's match. If it does, the step is marked complete. A single observation can complete at most one step per expedition but can progress multiple expeditions simultaneously.

The phone highlights one focused incomplete expedition as the active quest, but
that is a kid-facing game-flow choice rather than a dispatcher limit. Content
authors should still assume an observation may quietly advance other started
expeditions when their next steps also match.

**Matching is deliberately simple.** The match language is a small declarative vocabulary interpreted by the matcher registry in `app/matchers/`, not a full expression engine. If a match you want to express can't be written with one of the kinds below, the answer is usually "add a new kind" (small, tested, reviewable) not "invent a DSL."

### Match kinds

| Kind                          | When to reach for it                                    |
|-------------------------------|---------------------------------------------------------|
| `iconic_taxon`                | Broad category like Plantae, Insecta, Aves, Fungi       |
| `taxon_id`                    | A specific species or genus from iNaturalist            |
| `taxon_set`                   | Curated ecology groups like pollinators, decomposers, deciduous trees, semi-aquatic animals, or U.S. common invasives |
| `any_organism`                | Wildcard — any living observation counts                |
| `not_in_dex`                  | Nudge toward finding something new to the user          |
| `not_in_current_expedition`   | Require a different species than earlier completed steps in this expedition |
| `not_within_radius_of_existing` | Nudge toward geographic variety                       |
| `observation_tag`             | Match a closed-choice kid-selected tag such as a plant life stage |

#### `iconic_taxon`

Matches if the observation's taxon belongs to one of iNaturalist's top-level iconic categories. The most useful kind for starter expeditions because it's forgiving.

```json
{ "kind": "iconic_taxon", "value": "Plantae" }
```

Valid values: `Plantae`, `Insecta`, `Aves`, `Mammalia`, `Reptilia`, `Amphibia`, `Actinopterygii` (ray-finned fish), `Mollusca`, `Arachnida`, `Fungi`, `Chromista`, `Protozoa`, `Animalia` (catch-all for animals not in a more specific iconic taxon).

#### `taxon_id`

Matches a specific iNat taxon or anything under it in the taxonomic tree. Use when an expedition is themed around a clade.

```json
{ "kind": "taxon_id", "value": 47157, "include_descendants": true }
```

Looking up the right `value`: search the species on [iNaturalist](https://www.inaturalist.org) and copy the numeric ID from the URL (`/taxa/47157` → `47157`). Put the common and scientific name in a comment at the top of the expedition file for future-you. `include_descendants: true` is the common case ("any butterfly" = taxon ID for order Lepidoptera, descendants included).

#### `taxon_set`

Matches one of the manually curated groups in `content/expedition_taxon_sets.json`. The set file is intentionally small and reviewed by hand; every entry must carry `taxon_id_verified: true` so content authors can see which IDs were checked against iNaturalist.

```json
{ "kind": "taxon_set", "value": "pollinators", "include_descendants": true }
```

Use this for ecology quests where a single iNaturalist taxon is too narrow: `pollinators`, `decomposers`, `deciduous_trees`, `semi_aquatic_animals`, and `us_common_invasives`.

#### `any_organism`

Matches anything. Use for wildcard slots in starter expeditions where the goal is momentum, not specificity.

```json
{ "kind": "any_organism" }
```

No other fields. Seemingly trivial, but it's the difference between a kid completing their first expedition and giving up on step 3.

#### `not_in_dex`

Matches any observation of a species not already in this user's Dex. Use to encourage new finds, especially in tier-2+ expeditions where repeat-find grinding would be boring.

```json
{ "kind": "not_in_dex" }
```

#### `not_in_current_expedition`

Matches only when the current observation's taxon has not already completed an earlier step in this expedition run. Use this with `all_of` for "find three different deciduous trees" or "find three different pollinators." It requires a real `taxon_id`; manual/no-match observations will not satisfy it.

```json
{
  "kind": "all_of",
  "matches": [
    { "kind": "taxon_set", "value": "deciduous_trees" },
    { "kind": "not_in_current_expedition" }
  ]
}
```

#### `not_within_radius_of_existing`

Matches any observation at least `radius_meters` away from any prior observation by this user. Use to push kids to explore rather than photograph the same tree.

```json
{ "kind": "not_within_radius_of_existing", "radius_meters": 50 }
```

#### `observation_tag`

Matches a closed-choice ecology tag saved with the observation. The current approved tag key is `life_stage`, with values `flower`, `fruit_seed`, `seedling`, `leaf`, `adult`, and `egg_larva_nymph`. Do not use free text here; the mobile flow renders the options from the step's `tag_prompt`.

```json
{
  "kind": "observation_tag",
  "key": "life_stage",
  "value": "flower"
}
```

A step that uses `observation_tag` should include a matching prompt:

```json
{
  "tag_prompt": {
    "key": "life_stage",
    "question": "What stage can you see?",
    "options": [
      { "value": "flower", "label": "Flower" },
      { "value": "fruit_seed", "label": "Fruit or seeds" }
    ]
  }
}
```

### Composing kinds

A match spec can be wrapped in `all_of` or `any_of` to combine:

```json
{
  "kind": "all_of",
  "matches": [
    { "kind": "iconic_taxon", "value": "Plantae" },
    { "kind": "not_in_dex" }
  ]
}
```

This matches "a plant the kid hasn't logged before." Combinators nest; keep nesting shallow (two levels max) or the step becomes hard to reason about.

## Prerequisites

The `prerequisites` field on the top-level expedition controls when it becomes visible. Empty list = always available. The Phase 1 prerequisite kinds:

```json
{ "kind": "dex_count_at_least", "value": 5 }
```

Kid must have at least 5 species in their Dex. Used to gate tier-2 expeditions behind tier-1 completion.

```json
{ "kind": "completed_expedition", "value": "backyard_starter" }
```

Kid must have completed the named expedition. Used for direct-sequel expeditions.

Prerequisites are ANDed together: all must be satisfied for the expedition to become startable. If `preview_enabled` is true, the expedition may still appear in the locked preview shelf with `unlock_hint`; otherwise it stays hidden until unlocked.

## Validation

Every expedition file is validated against a Pydantic model at three points:

1. **Author-time**: `make validate-content` runs the validator across `content/expeditions/` and reports broken files.
2. **CI**: `.github/workflows/content-validate.yml` runs the same check on every PR. A broken expedition fails the build and never merges.
3. **App boot**: at API startup, the matcher registry rejects any match `kind` not registered in code. Boot fails loudly rather than serving a broken expedition at runtime.

The canonical model (source of truth — the doc follows this, not the other way around):

```python
# backend/app/models/expedition.py
from typing import Annotated, Literal, Union
from pydantic import BaseModel, Field, field_validator

IconicTaxon = Literal[
    "Plantae", "Insecta", "Aves", "Mammalia", "Reptilia", "Amphibia",
    "Actinopterygii", "Mollusca", "Arachnida", "Fungi", "Chromista",
    "Protozoa", "Animalia",
]

class MatchIconicTaxon(BaseModel):
    kind: Literal["iconic_taxon"]
    value: IconicTaxon

class MatchTaxonId(BaseModel):
    kind: Literal["taxon_id"]
    value: int
    include_descendants: bool = True

class MatchTaxonSet(BaseModel):
    kind: Literal["taxon_set"]
    value: str
    include_descendants: bool = True

class MatchAnyOrganism(BaseModel):
    kind: Literal["any_organism"]

class MatchNotInDex(BaseModel):
    kind: Literal["not_in_dex"]

class MatchNotInCurrentExpedition(BaseModel):
    kind: Literal["not_in_current_expedition"]

class MatchNotWithinRadius(BaseModel):
    kind: Literal["not_within_radius_of_existing"]
    radius_meters: Annotated[int, Field(ge=1, le=10_000)]

class MatchObservationTag(BaseModel):
    kind: Literal["observation_tag"]
    key: Literal["life_stage"]
    value: str

class MatchAllOf(BaseModel):
    kind: Literal["all_of"]
    # min_length: an empty all_of would vacuously match ANY photo
    matches: Annotated[list["MatchSpec"], Field(min_length=1)]  # forward ref

class MatchAnyOf(BaseModel):
    kind: Literal["any_of"]
    matches: Annotated[list["MatchSpec"], Field(min_length=1)]

MatchSpec = Annotated[
    Union[
        MatchIconicTaxon, MatchTaxonId, MatchAnyOrganism,
        MatchNotInDex, MatchNotWithinRadius,
        MatchTaxonSet, MatchNotInCurrentExpedition, MatchObservationTag,
        MatchAllOf, MatchAnyOf,
    ],
    Field(discriminator="kind"),
]

class EcologyTagOption(BaseModel):
    value: str
    label: str

class StepTagPrompt(BaseModel):
    key: Literal["life_stage"]
    question: str
    options: Annotated[list[EcologyTagOption], Field(min_length=2, max_length=6)]

class Step(BaseModel):
    id: str
    description: str
    match: MatchSpec
    hint: str | None = None
    tag_prompt: StepTagPrompt | None = None

class PrereqDexCount(BaseModel):
    kind: Literal["dex_count_at_least"]
    value: int

class PrereqCompleted(BaseModel):
    kind: Literal["completed_expedition"]
    value: str

Prerequisite = Annotated[
    Union[PrereqDexCount, PrereqCompleted],
    Field(discriminator="kind"),
]

class Expedition(BaseModel):
    id: str
    title: str
    subtitle: str | None = None
    tier: Annotated[int, Field(ge=1, le=5)]
    duration_minutes: Annotated[int, Field(ge=5, le=120)]
    environments: list[Literal["yard", "park", "street", "school", "other"]]
    theme: Literal[
        "warmup", "food_web", "pollinators", "decomposers", "trees",
        "wetland", "invasive", "urban", "seasonal",
    ] = "warmup"
    learning_goal: str | None = None
    difficulty_label: str | None = None
    preview_enabled: bool = False
    unlock_hint: str | None = None
    intro: str
    outro: str
    prerequisites: list[Prerequisite] = []
    steps: Annotated[list[Step], Field(min_length=1, max_length=5)]

    @field_validator("id")
    @classmethod
    def id_is_snake_case(cls, v: str) -> str:
        if not v.replace("_", "").isalnum() or v != v.lower():
            raise ValueError("id must be lowercase snake_case")
        return v
```

A matching JSON Schema lives at `content/schema/expedition.schema.json` (generated from the Pydantic model via `scripts/regenerate_schema.py`). Point your editor at it for autocomplete and inline validation while authoring.

## Sync pipeline

The repo is the source of truth. Postgres is a materialized view. The only write path is deploy.

```
content/expeditions/*.json
         │
         ▼  (validated in CI: content-validate.yml)
  hinterland-api image build         — repo-root context bakes content into the image
         │
         ▼  (Container Apps Job `hinterland-sync-expeditions`, started after each deploy when provisioned)
  admin/sync_expeditions.py  ───────▶  Postgres (`expedition_content` table)
         │
         ├─ validates every file with the Pydantic model (any broken file aborts the run)
         ├─ computes content_hash per file
         ├─ skips rows whose hash hasn't changed
         └─ never deletes and never resurrects (tombstoning = the `archived` flag; revival = `--unarchive`)
```

`scripts/sync_expeditions.py` is the local shim around the same module, pointed at the repo checkout instead of the baked-in `/app/content/expeditions`.

**Never edit `expedition_content` rows directly.** The rule is enforced by habit, not by grants (that's an overreaction for a solo build), but the moment two authors exist it becomes a real constraint. Lose the source of truth in the repo and you lose reproducibility, PR review, and the ability to roll back.

**Never edit the `id` of a live expedition.** Expedition progress is keyed on `(user_id, expedition_id)`. Change the id and every kid's progress vanishes from the UI. If an expedition needs retiring, tombstone it (set the row's `archived` flag — see runbook) rather than renaming; the sync job's `--unarchive <id>` flag revives it later.

## Adding a new match kind — the recipe

Follows the same pattern as adding a dispatcher handler: small, local, reviewed.

1. **Define the spec.** Add a new `Match<Name>` Pydantic model in `models/expedition.py`. Add it to the `MatchSpec` union. This is the only place the schema is defined.
2. **Implement the matcher.** Add a file in `app/matchers/kinds/<name>.py` with a function that takes `(spec: Match<Name>, inputs: MatcherInputs) -> bool`. Keep it pure — no DB calls inside individual matcher functions.
3. **Register it.** One line in `app/matchers/registry.py`.
4. **Test it.** Unit test the matcher against 5–10 observation fixtures covering positive, negative, and edge cases (e.g. missing fields in the observation). Snapshot-test an expedition that uses it through the dispatcher test harness.
5. **Document it.** Add a row to the match kinds table above, with an example.
6. **Regenerate the JSON Schema.** `python scripts/regenerate_schema.py`. Commit both the Pydantic change and the schema regeneration in the same PR.

No step 7. No touching `ExpeditionHandler` — it dispatches against the registry, never against specific kinds.

## Voice and tone

The copy a kid reads matters as much as the mechanics. A few principles that should survive every author edit:

**Respect the reader.** Kids 9–12 know when they're being talked down to. "Even the most familiar place is full of life you've never noticed" trusts them; "Let's have fun exploring the outdoors!" does not.

**Show, don't abstract.** Hints should be concrete examples, not categories. "Grass, a weed in a sidewalk crack, a tree, a houseplant by a window — all count" beats "Plants are everywhere — keep your eyes open!"

**Name the science.** Every outro should remind the kid that what they just did was real. "You just contributed real data to science" is the load-bearing sentence. Don't hedge it with "kind of" or "in a way."

**No exclamation point inflation.** One per expedition at most, usually in the outro. Excitement on every line numbs to neutrality.

**Avoid gendered or culturally-specific defaults.** "Your yard" excludes apartment kids; "wherever you're standing" doesn't. "Mom and Dad" excludes many families; "your grown-up" covers all of them.

**Length targets.** Intro: 1–2 sentences. Outro: 1 sentence. Step description: under 10 words. Hint: under 20 words. Brevity is a feature for this audience.

## Starter expedition catalog

Starter expeditions are tier 1, have no prerequisites, and should be visible immediately. The first mission stays easy, but the catalog should quickly signal real ecology themes.

1. **`backyard_starter.json` — Start Where You Are.** Warm-up: plant / insect / surprise organism. This is the default first quest and works anywhere.

2. **`park_starter.json` — Park Patrol.** Tree / flying animal / ground-level new find. A gentle park ecology bridge.

3. **`street_starter.json` — Sidewalk Science.** Plant / insect / bird in an urban habitat.

4. **`school_starter.json` — Schoolyard Survey.** Fence / doorway / distance-based find to show that a schoolyard has microhabitats.

5. **`anywhere_starter.json` — Food Web Anywhere.** Producer / consumer / recycler. This replaces the old generic warm-up copy with a specific food-web learning goal.

6. **`pollinator_scout.json` — Pollinator Scout.** Flower / pollinator / different pollinator. Uses `taxon_set: pollinators` plus `not_in_current_expedition`.

7. **`decomposer_detectives.json` — Decomposer Detectives.** Fungi / detritivore / different decomposer. Uses `taxon_set: decomposers`.

8. **`tree_trio.json` — Tree Trio.** Three different deciduous trees. Uses `taxon_set: deciduous_trees` plus `not_in_current_expedition`.

## Locked preview catalog

Tier-2 expeditions can be locked but visible when `preview_enabled` is true. The board uses these as a shelf that shows the educational arc before a kid unlocks everything.

1. **`backyard_closeup.json` — Look Closer.** Small backyard species and a new plant.

2. **`park_pollinators.json` — Pollinator Patrol.** Bloom / Lepidoptera / Hymenoptera / new pollinator.

3. **`street_survivors.json` — Urban Survivors.** City animals and pavement plants.

4. **`school_census.json` — Schoolyard Census.** Fungi, insects, birds, and a wider schoolyard search radius.

5. **`anywhere_collector.json` — Nothing But New.** New-to-Dex observations with a distance challenge.

6. **`food_chain_builder.json` — Food Chain Builder.** Producer / plant eater / predator-or-scavenger / decomposer.

7. **`wetland_watch.json` — Wetland Watch.** Semi-aquatic animals, with copy that tells kids to stay safe and observe from paths or edges.

8. **`us_invasive_watch.json` — U.S. Invasive Watch.** U.S.-labeled common invasive species. Keep the regional label; do not imply a taxon is globally invasive.

9. **`life_cycle_builder.json` — Life Cycle Builder.** Uses `observation_tag` with closed-choice plant life-stage prompts. It should never guess life stage from AI or free text.
