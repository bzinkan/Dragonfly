/**
 * Pure decision logic for whether the 3D Sanctuary renders. Kept free of
 * React/Expo imports so it is trivially unit-testable.
 *
 * The 2D screen is the permanent fallback (ADR 0011): any "no" here lands
 * on Sanctuary2DScreen, never on a broken canvas.
 */

/** GL crashes tolerated before the session pins to 2D until an app update. */
export const MAX_GL_CRASHES = 3;

export type Sanctuary3DDecisionInput = {
  /** Build-time SANCTUARY_3D flag (eas.json env -> extra.sanctuary3d). */
  buildFlagEnabled: boolean;
  /** TalkBack/VoiceOver active: the text-first 2D screen is strictly better. */
  screenReaderEnabled: boolean;
  /** Kid-facing "Simple view" escape hatch in Settings. */
  simpleViewPreferred: boolean;
  /** Persisted count of GL crashes / mount-watchdog trips. */
  crashCount: number;
};

export function decideSanctuary3D(input: Sanctuary3DDecisionInput): boolean {
  return (
    input.buildFlagEnabled &&
    !input.screenReaderEnabled &&
    !input.simpleViewPreferred &&
    input.crashCount < MAX_GL_CRASHES
  );
}
