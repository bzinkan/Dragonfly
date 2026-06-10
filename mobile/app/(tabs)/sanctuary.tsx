/**
 * Sanctuary tab route: flag chooser between the 3D living diorama
 * (ADR 0011) and the permanent 2D screen.
 *
 * The 2D screen is the fallback for every "no": build flag off
 * (play-internal/production until the post-pilot flag flip), screen reader
 * active, "Simple view" preferred, or the GL crash latch tripped. The 3D
 * screen additionally falls back to 2D in place on canvas errors.
 */

import React from "react";

import { useSanctuary3DFlag } from "@/src/config/featureFlags";
import Sanctuary2DScreen from "@/src/sanctuary/Sanctuary2DScreen";
import Sanctuary3DScreen from "@/src/sanctuary3d/Sanctuary3DScreen";

export default function SanctuaryTab() {
  const sanctuary3D = useSanctuary3DFlag();
  return sanctuary3D ? <Sanctuary3DScreen /> : <Sanctuary2DScreen />;
}
