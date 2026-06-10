/**
 * Runtime feature-flag resolution. Currently: the Sanctuary 3D diorama
 * (ADR 0011).
 *
 * Layering: build-time SANCTUARY_3D (eas.json -> app.config.ts extra)
 * is the hard gate; runtime conditions (screen reader, Simple view pref,
 * GL crash latch) can only turn 3D OFF, never on.
 */

import Constants from "expo-constants";
import { useEffect, useState } from "react";
import { AccessibilityInfo } from "react-native";

import { decideSanctuary3D } from "@/src/sanctuary3d/flagDecision";
import { useSanctuary3DPrefs } from "@/src/sanctuary3d/prefs";

const extra = Constants.expoConfig?.extra as { sanctuary3d?: boolean } | undefined;

/** Build-time flag value (stable for the life of the binary). */
export const SANCTUARY_3D_BUILD_FLAG = extra?.sanctuary3d === true;

function useScreenReaderEnabled(): boolean {
  const [enabled, setEnabled] = useState(false);
  useEffect(() => {
    let mounted = true;
    void AccessibilityInfo.isScreenReaderEnabled().then((value) => {
      if (mounted) setEnabled(value);
    });
    const subscription = AccessibilityInfo.addEventListener(
      "screenReaderChanged",
      setEnabled,
    );
    return () => {
      mounted = false;
      subscription.remove();
    };
  }, []);
  return enabled;
}

/** True when the Sanctuary tab should render the 3D diorama. */
export function useSanctuary3DFlag(): boolean {
  const screenReaderEnabled = useScreenReaderEnabled();
  const simpleViewPreferred = useSanctuary3DPrefs((s) => s.simpleView);
  const crashCount = useSanctuary3DPrefs((s) => s.crashCount);
  return decideSanctuary3D({
    buildFlagEnabled: SANCTUARY_3D_BUILD_FLAG,
    screenReaderEnabled,
    simpleViewPreferred,
    crashCount,
  });
}
