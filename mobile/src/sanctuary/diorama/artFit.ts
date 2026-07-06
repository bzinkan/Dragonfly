/**
 * Art-fit constants: how the generated art maps into island-local canvas
 * units. Promoted to pure core in D7 (the D4 spike carried private copies;
 * the spike stays frozen with its own values) so the renderer, hitTest,
 * and framing all derive from ONE description of the drawn geometry --
 * that is what closes the D4 gap where the tap radius (36) and the painted
 * plateau (~61 units) disagreed.
 *
 * Two art sources, two unit mappings:
 *  - Island layer art (islandLayers.gen.ts): 512x384 px, bottom-center
 *    anchored at the island slot.
 *  - Sprite art (sprites.gen.ts): 128x128 px canvases, feet on the
 *    bottom-center anchor.
 *
 * No React, no Skia -- everything here is unit-tested plain data.
 */

/** Generated island layer canvas, px (islandLayers.gen.ts contract). */
export const LAYER_ART_PX = { width: 512, height: 384 } as const;

/** Island layer px -> island-local canvas units. */
export const LAYER_UNITS_PER_PX = 0.24;

/** Drawn layer size in island-local units. */
export const LAYER_W = LAYER_ART_PX.width * LAYER_UNITS_PER_PX;
export const LAYER_H = LAYER_ART_PX.height * LAYER_UNITS_PER_PX;

/** Art bottom edge sits this far below the island anchor (local units). */
export const LAYER_BOTTOM_Y = 44;

/** Island-local rect the 512x384 layer art is drawn into. */
export const LAYER_RECT = {
  x: -LAYER_W / 2,
  y: LAYER_BOTTOM_Y - LAYER_H,
  width: LAYER_W,
  height: LAYER_H,
} as const;

/**
 * Half-width of the painted plateau in island-local units (61.44). The
 * island tap radius derives from this so the visible island edge is
 * always tappable (D4 finding d).
 */
export const ISLAND_ART_HALF_WIDTH = LAYER_W / 2;

/** Sprite art px -> island-local units (128px canvas ~= a 30-unit body). */
export const SPRITE_UNITS_PER_PX = 0.24;

/**
 * Sprite scale hierarchy (D4 finding e): on device, flower accents drew as
 * large as bushes and the island read as clip-art. The fix lives in the
 * draw-scale path (never in the generated art): every sprite draw is
 * multiplied by its class factor below, establishing canopy > shrub >
 * ground-minor > flora-accent.
 */
export const SPRITE_CLASS_SCALE = {
  /** Trees and pines: the big silhouette masses. Reference scale. */
  canopy: 1,
  /** Bushes: clearly beneath the canopy. */
  shrub: 0.85,
  /** Rocks and stumps: ground furniture. */
  minor: 0.75,
  /** Flowers and mushrooms: small dressing accents, not inhabitants. */
  accent: 0.55,
} as const;

export type SpriteScaleClass = keyof typeof SPRITE_CLASS_SCALE;

/**
 * Scenery (tier-dressing) manifest name -> scale class. Every key used by
 * DRESSING_RULES must appear here (unit-tested); unknown names fall back
 * to canopy (multiplier 1) so a new asset is never invisible.
 */
export const SCENERY_SCALE_CLASS: Record<string, SpriteScaleClass> = {
  "tree-default": "canopy",
  "tree-oak": "canopy",
  "tree-thin": "canopy",
  "tree-detailed": "canopy",
  "pine-round": "canopy",
  "pine-tall": "canopy",
  bush: "shrub",
  "bush-large": "shrub",
  "stump-round": "minor",
  "rock-large-a": "minor",
  "rock-large-c": "minor",
  "rock-tall-b": "minor",
  "rock-small-a": "minor",
  "rock-small-d": "minor",
  "flower-purple": "accent",
  "flower-yellow": "accent",
  "flower-red": "accent",
  "mushroom-group": "accent",
};

/**
 * Draw-scale multiplier for one placed sprite. Elements and souvenirs are
 * inhabitants/keepsakes and keep their authored presence (1); scenery is
 * classed by name.
 */
export function spriteScaleMultiplier(
  kind: "element" | "scenery" | "souvenir",
  sceneryName: string,
): number {
  if (kind !== "scenery") return 1;
  const cls = SCENERY_SCALE_CLASS[sceneryName];
  return cls === undefined ? SPRITE_CLASS_SCALE.canopy : SPRITE_CLASS_SCALE[cls];
}
