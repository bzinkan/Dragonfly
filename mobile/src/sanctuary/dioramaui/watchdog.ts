/**
 * Render watchdog for the diorama screen (pure state machine; the screen
 * wires timers/error boundaries around it). Same semantics as the 3D
 * crash latch (ADR 0011): a canvas that crashes OR never produces a first
 * frame within the timeout counts as ONE strike; strikes persist via
 * prefs.recordRenderCrash, and decideSanctuaryDiorama pins the tab to the
 * classic screen at MAX_RENDER_CRASHES.
 *
 * The machine guarantees at most one strike per canvas mount: only the
 * transition INTO "tripped" is a strike, and "tripped" is absorbing.
 */

/** A canvas that has not drawn within this window counts as a strike. */
export const FIRST_FRAME_TIMEOUT_MS = 8000;

export type WatchdogPhase = "waiting" | "passed" | "tripped";

export type WatchdogEvent =
  /** The first UI-thread frame ticked after the canvas mounted. */
  | "first-frame"
  /** The first-frame timer fired. */
  | "timeout"
  /** The render error boundary caught a canvas crash. */
  | "crash";

/** Advance the watchdog. Pure; total over all (phase, event) pairs. */
export function reduceWatchdog(
  phase: WatchdogPhase,
  event: WatchdogEvent,
): WatchdogPhase {
  if (phase === "tripped") return "tripped"; // absorbing: one strike max
  if (event === "crash") return "tripped"; // crashes count even post-frame
  if (phase === "waiting") {
    if (event === "first-frame") return "passed";
    return "tripped"; // timeout with no frame yet
  }
  // passed: a late timeout is a no-op.
  return "passed";
}

/** True exactly when this transition should record a persisted strike. */
export function isStrikeTransition(
  prev: WatchdogPhase,
  next: WatchdogPhase,
): boolean {
  return next === "tripped" && prev !== "tripped";
}
