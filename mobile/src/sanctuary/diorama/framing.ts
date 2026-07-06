/**
 * Camera framings for the two diorama modes: the whole-archipelago vista
 * and the single-island dive. A framing names the canvas point to center
 * in the viewport and the zoom to show it at; the render layer animates
 * between framings but never computes them -- these stay pure and
 * unit-tested.
 *
 * D7: the dive zoom is DERIVED, not authored. On device (D4 finding c)
 * fixed per-zone zooms left small islands swimming in sky and big ones
 * cropped; deriving the scale from the painted plateau width guarantees
 * every dive fills the same fraction of the screen regardless of the
 * island's vista scale.
 */

import type { SanctuaryZoneId } from "@/src/api/sanctuary";
import { ISLAND_ART_HALF_WIDTH } from "@/src/sanctuary/diorama/artFit";
import {
  ISLAND_SLOTS,
  REFERENCE_SCREEN_WIDTH,
  VISTA_CANVAS,
} from "@/src/sanctuary/diorama/vistaLayout";

/** A camera target: center this canvas point at this zoom. */
export type Framing = {
  x: number;
  y: number;
  scale: number;
};

/**
 * A dive frames the painted island plateau across this fraction of the
 * screen width (Brian's art direction: ~85-90%).
 */
export const DIVE_FILL_FRACTION = 0.875;

/**
 * Dive zoom for a zone: the scale at which the island's painted plateau
 * (2 x ISLAND_ART_HALF_WIDTH x islandScale canvas units) spans
 * DIVE_FILL_FRACTION of the reference screen.
 */
export function diveScaleFor(zoneId: SanctuaryZoneId): number {
  const plateau = 2 * ISLAND_ART_HALF_WIDTH * ISLAND_SLOTS[zoneId].islandScale;
  return (DIVE_FILL_FRACTION * REFERENCE_SCREEN_WIDTH) / plateau;
}

/** The vista framing: whole canvas centered at 1:1 zoom. */
export function vistaFraming(): Framing {
  return {
    x: VISTA_CANVAS.width / 2,
    y: VISTA_CANVAS.height / 2,
    scale: 1,
  };
}

/** The dive framing for a zone: its island slot centered, zoomed in. */
export function zoneFraming(zoneId: SanctuaryZoneId): Framing {
  const slot = ISLAND_SLOTS[zoneId];
  return {
    x: slot.x,
    y: slot.y,
    scale: diveScaleFor(zoneId),
  };
}
