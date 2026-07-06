/**
 * Tap vs pan discrimination for the diorama's PanResponder (pure, unit
 * tested). D4 device finding a: a fast fling can travel only a few dp
 * before release, so movement slop ALONE misclassifies flings as taps.
 * A release is a tap only when BOTH the total movement and the release
 * velocity are small.
 */

/** Release movement under this many dp can still be a tap. */
export const TAP_SLOP = 8;

/**
 * Release speed under this (dp per ms, the PanResponder gestureState
 * velocity unit) can still be a tap. A deliberate fling releases well
 * above ~0.3 dp/ms even when dx is tiny.
 */
export const TAP_MAX_SPEED = 0.3;

export type ReleaseGesture = {
  /** Total movement since grant, dp. */
  dx: number;
  dy: number;
  /** Velocity at release, dp/ms. */
  vx: number;
  vy: number;
};

/** Classify a PanResponder release. */
export function classifyRelease(g: ReleaseGesture): "tap" | "pan" {
  const moved = Math.hypot(g.dx, g.dy);
  const speed = Math.hypot(g.vx, g.vy);
  return moved < TAP_SLOP && speed < TAP_MAX_SPEED ? "tap" : "pan";
}
