/**
 * ScenePalette + zone placeholder colors -> the 12 generated-art palette
 * slots (SANCTUARY_PALETTE_SLOTS), plus the dormant saturation matrix.
 * Pure data mapping -- the render layer feeds the result to svgCache and
 * never hand-picks hexes itself, so a season change is one palette swap.
 *
 * Slot sources follow the islandLayers.gen.ts header contract:
 *   horizon    tracks ScenePalette.horizon
 *   glow       tracks the ScenePalette.sunColor family
 *   green_mid  tracks ScenePalette.ground
 *   accent_*   track season.zone_accents at dive time (D6+); until then
 *              they hold the spring-neutral baseline
 * Slots without a ScenePalette source draw from the zone placeholder
 * palette (same hue families) or the generator's spring-neutral baseline.
 */

import type { SanctuaryZoneId } from "@/src/api/sanctuary";
import {
  SANCTUARY_PALETTE_SLOTS,
  type SanctuaryPaletteSlot,
} from "@/src/sanctuary/art/islandLayers.gen";
import {
  SILHOUETTE_COLOR,
  ZONE_ACCENT_COLOR,
  ZONE_PLACEHOLDER_COLOR,
} from "@/src/sanctuary/diorama/scene/zoneColors";
import type { ScenePalette } from "@/src/sanctuary/diorama/season/palette";
import type { SlotHexes } from "@/src/sanctuary/dioramaui/svgCache";

/** Spring-neutral baseline for slots with no live palette source yet
 * (author/lib/tokens.mjs values, per the generated-art header). */
const BASELINE: Pick<
  Record<SanctuaryPaletteSlot, string>,
  "sand" | "earth_mid" | "accent_warm" | "accent_cool"
> = {
  sand: "#D9C79A",
  earth_mid: "#8A6B4A",
  accent_warm: "#E2793F",
  accent_cool: "#8C7BC9",
};

/** Concrete hex for every generated-art palette slot. */
export function paletteSlotHexes(palette: ScenePalette): SlotHexes {
  return {
    green_mid: palette.ground,
    green_deep: ZONE_ACCENT_COLOR.woodland,
    bark: ZONE_PLACEHOLDER_COLOR.soil,
    sand: BASELINE.sand,
    earth_mid: BASELINE.earth_mid,
    earth_deep: ZONE_ACCENT_COLOR.soil,
    water: ZONE_PLACEHOLDER_COLOR.pond,
    accent_warm: BASELINE.accent_warm,
    accent_cool: BASELINE.accent_cool,
    glow: palette.sunColor,
    cloud: ZONE_PLACEHOLDER_COLOR.sky,
    horizon: palette.horizon,
  };
}

/**
 * Dive-time slots for one island: the zone-accent slots pick up the dived
 * zone's identity (contract 5 -- D4 left green_deep pinned to the woodland
 * accent for every island; here the deep-foliage tone follows the dived
 * zone). Only the dived island re-records with these; vista islands keep
 * the base mapping.
 */
export function zoneAccentSlotHexes(
  palette: ScenePalette,
  zoneId: SanctuaryZoneId,
): SlotHexes {
  return {
    ...paletteSlotHexes(palette),
    green_deep: ZONE_ACCENT_COLOR[zoneId],
  };
}

/** Dormant saturation: "asleep, not locked" (ADR 0012 / D4 spike value). */
export const DORMANT_SAT = 0.12;

/** Rec. 709 luma weights for the saturation matrix. */
const LUMA_R = 0.2126;
const LUMA_G = 0.7152;
const LUMA_B = 0.0722;

/**
 * 4x5 color matrix that lerps toward luminance grey: s = 1 is the exact
 * identity, s ~ 0.12 is the dormant "asleep, not locked" look. The offset
 * column adds a slight warm bias (scaled by 1 - s, so it vanishes at
 * identity) -- dormant islands read as dusty parchment, not corpse grey.
 * Worklet-safe: driven per-frame by the wake animation's shared value.
 */
export function satMatrix(s: number): number[] {
  "worklet";
  const inv = 1 - s;
  return [
    LUMA_R * inv + s, LUMA_G * inv,     LUMA_B * inv,     0, 0.032 * inv,
    LUMA_R * inv,     LUMA_G * inv + s, LUMA_B * inv,     0, 0.014 * inv,
    // `+ 0` normalizes -0 at s = 1 so the identity case is exact.
    LUMA_R * inv,     LUMA_G * inv,     LUMA_B * inv + s, 0, -0.02 * inv + 0,
    0,                0,                0,                1, 0,
  ];
}

// ---------------------------------------------------------------------------
// Hex-space color math. The generated art carries NO literal colors -- every
// fill/stop is a {{slot}} token -- so applying satMatrix to the 12 slot
// hexes in JS and re-substituting yields exactly the dormant look WITHOUT a
// per-frame saveLayer: satMatrix is affine and gradient/AA interpolation is
// convex, so matrix-then-substitute equals substitute-then-ColorMatrix.
// ---------------------------------------------------------------------------

function hexChannel(v: number): string {
  const clamped = Math.max(0, Math.min(255, Math.round(v * 255)));
  return clamped.toString(16).padStart(2, "0").toUpperCase();
}

function parseHex(hex: string): [number, number, number] {
  const r = parseInt(hex.slice(1, 3), 16) / 255;
  const g = parseInt(hex.slice(3, 5), 16) / 255;
  const b = parseInt(hex.slice(5, 7), 16) / 255;
  return [r, g, b];
}

/** Apply a 4x5 color matrix (satMatrix layout) to one #RRGGBB hex. */
export function applyColorMatrixToHex(hex: string, m: number[]): string {
  const [r, g, b] = parseHex(hex);
  const outR = m[0] * r + m[1] * g + m[2] * b + m[3] + m[4];
  const outG = m[5] * r + m[6] * g + m[7] * b + m[8] + m[9];
  const outB = m[10] * r + m[11] * g + m[12] * b + m[13] + m[14];
  return `#${hexChannel(outR)}${hexChannel(outG)}${hexChannel(outB)}`;
}

/**
 * Dormant slot mapping: every slot desaturated through satMatrix(s). The
 * render layer records dormant islands from these hexes once, so the
 * steady-state vista pays zero layer cost for sleeping zones and the art
 * stays vector-crisp when a dormant island is dived.
 */
export function dormantSlotHexes(
  slots: SlotHexes,
  s: number = DORMANT_SAT,
): SlotHexes {
  const m = satMatrix(s);
  const out = {} as SlotHexes;
  for (const slot of SANCTUARY_PALETTE_SLOTS) {
    out[slot] = applyColorMatrixToHex(slots[slot], m);
  }
  return out;
}

/** Linear mix of two #RRGGBB hexes (t = 0 -> a, t = 1 -> b). */
export function mixHex(a: string, b: string, t: number): string {
  const [ar, ag, ab] = parseHex(a);
  const [br, bg, bb] = parseHex(b);
  return `#${hexChannel(ar + (br - ar) * t)}${hexChannel(
    ag + (bg - ag) * t,
  )}${hexChannel(ab + (bb - ab) * t)}`;
}

/**
 * Silhouette tint: every slot collapses to ONE dark tone (an SrcIn-style
 * flat tint achieved through token substitution, so the hint needs no
 * per-frame layer or blend). Lifting the tint slightly toward the horizon
 * color reads as "translucent shape in the haze" over the desaturated
 * dormant island.
 */
export function silhouetteSlotHexes(slots: SlotHexes): SlotHexes {
  const tint = mixHex(SILHOUETTE_COLOR, slots.horizon, 0.3);
  const out = {} as SlotHexes;
  for (const slot of SANCTUARY_PALETTE_SLOTS) {
    out[slot] = tint;
  }
  return out;
}
