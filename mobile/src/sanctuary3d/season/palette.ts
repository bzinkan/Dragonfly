/**
 * Season -> 3D scene palette. The API ships a season word and a
 * `background_tone` word (fresh | warm | fading | still); this module maps
 * them to sky/fog/light colors. Pure lookup -- unit-testable, no three
 * imports (colors are hex strings consumed by the scene layer).
 *
 * The seasonal MATERIAL palettes (recoloring zone models) live in the asset
 * pipeline (scripts/sanctuary_assets/palette/) and arrive with asset
 * milestone A8; this file only governs atmosphere.
 */

import type { SanctuarySeason } from "@/src/api/sanctuary";

export type ScenePalette = {
  /** Canvas clear color / sky dome. */
  sky: string;
  /** Distance fog color (matched near the sky for a soft horizon). */
  fog: string;
  /** Hemisphere light sky color. */
  hemiSky: string;
  /** Hemisphere light ground bounce color. */
  hemiGround: string;
  /** Directional sun intensity. */
  sunIntensity: number;
  /** Ground/base tint for the island placeholder until zone art lands. */
  ground: string;
};

const SEASON_BASE: Record<SanctuarySeason, ScenePalette> = {
  spring: {
    sky: "#BFDDF0",
    fog: "#CDE4F0",
    hemiSky: "#D6EAF7",
    hemiGround: "#7C9B62",
    sunIntensity: 1.35,
    ground: "#8FBC6F",
  },
  summer: {
    sky: "#A8CBE8",
    fog: "#BFD8EA",
    hemiSky: "#CFE3F2",
    hemiGround: "#6F934F",
    sunIntensity: 1.55,
    ground: "#7FAF5C",
  },
  autumn: {
    sky: "#C9CFE0",
    fog: "#D6D4DC",
    hemiSky: "#DCDDE6",
    hemiGround: "#8A7448",
    sunIntensity: 1.2,
    ground: "#A98E4F",
  },
  winter: {
    sky: "#C5D2DC",
    fog: "#D4DDE4",
    hemiSky: "#E0E7EC",
    hemiGround: "#7E8A90",
    sunIntensity: 1.0,
    ground: "#9FA8A4",
  },
};

/**
 * Tone adjustments layered on the season base. Unknown tones fall back to
 * the season base unchanged (the wire type is a plain string).
 */
const TONE_OVERRIDES: Record<string, Partial<ScenePalette>> = {
  fresh: { sunIntensity: 1.45 },
  warm: { sky: "#B9D2E2", fog: "#D8DCC9", sunIntensity: 1.6 },
  fading: { sky: "#CBC6D6", fog: "#DCD3D2", sunIntensity: 1.1 },
  still: { sky: "#C2CDD6", fog: "#D9E0E5", sunIntensity: 0.9 },
};

export function scenePalette(
  season: SanctuarySeason,
  backgroundTone: string,
): ScenePalette {
  const base = SEASON_BASE[season];
  const override = TONE_OVERRIDES[backgroundTone] ?? {};
  return { ...base, ...override };
}
