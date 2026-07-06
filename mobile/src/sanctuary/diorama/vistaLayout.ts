/**
 * The archipelago composition: where each zone's island sits on the wide
 * vista canvas, which parallax band it scrolls in, and how large it is
 * drawn. This is authored layout data (the "camera-ready" arrangement from
 * the 2.5D plan), not derived from the API -- pure constants, unit-tested.
 *
 * Canvas units are dp of a 390dp-wide reference screen. The vista is 2.5
 * screens wide (975 units) so horizontal panning reveals the archipelago;
 * the render layer scales canvas units to the actual device width.
 *
 * Bands (painter order back -> fore) drive both draw order and parallax:
 * far islands drift slower than the pan, foreground islands track it 1:1,
 * and the sky island barely moves at all.
 *
 * D7 retune (S21U device findings, Brian's 2.5D art direction): the D4
 * slots left woodland and elsewhere permanently outside the pannable
 * window, and every island read too small at vista. The slots below keep
 * every island's anchor inside its band's reachable window
 *   |x - 487.5| <= 195 + VISTA_PAN_LIMIT * parallax
 * (window = one 390-unit reference screen centered on the canvas, slid by
 * the clamped pan times the band's parallax), and the islandScales give
 * fore islands ~40-50% of the screen width -- staggered in depth so fore
 * islands partially occlude the rows behind as the camera pans.
 */

import type { SanctuaryZoneId } from "@/src/api/sanctuary";

/** Reference screen width, dp. Canvas units are dp on this screen. */
export const REFERENCE_SCREEN_WIDTH = 390;

/** Vista canvas size in canvas units (2.5 x 390dp wide, 2 x 390dp tall). */
export const VISTA_CANVAS = { width: 975, height: 780 } as const;

/**
 * Horizontal camera pan clamp, canvas units either side of center
 * (0.4 reference screens -- matches the D4 spike's feel on device).
 */
export const VISTA_PAN_LIMIT = 0.4 * REFERENCE_SCREEN_WIDTH;

/** Depth band an island belongs to (also its painter tier, back first). */
export type IslandBand = "back" | "mid" | "fore";

export type IslandSlot = {
  /** Island anchor (its local origin) on the vista canvas, canvas units. */
  x: number;
  y: number;
  band: IslandBand;
  /** Multiplier applied to island-local coordinates when drawn in the vista. */
  islandScale: number;
};

/**
 * Authored island slots. Composition (back -> front, left -> right):
 * elsewhere is the small misty islet top-left, woodland the back ridge
 * left-of-center, sky hangs high center-right, urban sits mid-right,
 * then the large fore row: meadow front-left, soil low-front-center
 * (overlapping meadow's skirt), pond front-right (overlapping soil).
 */
export const ISLAND_SLOTS: Record<SanctuaryZoneId, IslandSlot> = {
  meadow: { x: 330, y: 560, band: "fore", islandScale: 1.6 },
  woodland: { x: 420, y: 210, band: "back", islandScale: 0.95 },
  pond: { x: 660, y: 590, band: "fore", islandScale: 1.45 },
  sky: { x: 560, y: 110, band: "mid", islandScale: 0.75 },
  soil: { x: 490, y: 680, band: "fore", islandScale: 1.35 },
  urban: { x: 700, y: 330, band: "mid", islandScale: 1.05 },
  elsewhere: { x: 260, y: 140, band: "back", islandScale: 0.6 },
};

/**
 * Horizontal parallax per band, plus the sky island's own extra-slow
 * factor: fraction of the camera pan an island actually moves by.
 */
export const PARALLAX_FACTOR: Record<IslandBand | "sky", number> = {
  back: 0.35,
  mid: 0.7,
  fore: 1.0,
  sky: 0.1,
};

/**
 * Parallax factor for a zone's island: the sky island overrides its band
 * (it hangs in the far atmosphere), everything else follows its band.
 */
export function parallaxFor(zoneId: SanctuaryZoneId): number {
  if (zoneId === "sky") return PARALLAX_FACTOR.sky;
  return PARALLAX_FACTOR[ISLAND_SLOTS[zoneId].band];
}
