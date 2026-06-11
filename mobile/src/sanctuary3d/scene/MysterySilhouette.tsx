/**
 * Mystery cue rendered as a dark, faintly translucent shape at a dormant
 * zone's center -- "something lives here, come wake it." The cue's TEXT
 * stays in the Quiet Corners panel (docs/sanctuary.md §10: no answer
 * leakage on the model). Until zone art lands, the silhouette is a simple
 * per-zone form in the dormant palette.
 */

import React from "react";

import type { SanctuaryZoneId } from "@/src/api/sanctuary";
import { ZONE_LAYOUT } from "@/src/sanctuary3d/placement/zoneAnchors";
import { SILHOUETTE_COLOR } from "@/src/sanctuary3d/scene/zoneColors";
import { heightAt } from "@/src/sanctuary3d/terrain/heightfield";

const TERRAIN_ZONES = new Set<SanctuaryZoneId>([
  "meadow",
  "woodland",
  "pond",
  "urban",
]);

export function MysterySilhouette({ zoneId }: { zoneId: SanctuaryZoneId }) {
  const [cx, cy, cz] = ZONE_LAYOUT[zoneId].center;
  const y = TERRAIN_ZONES.has(zoneId) ? heightAt(cx, cz) : cy;
  if (zoneId === "pond") {
    return (
      <mesh position={[cx, y + 0.5, cz]}>
        <cylinderGeometry args={[0.4, 0.4, 0.06, 12]} />
        <meshLambertMaterial color={SILHOUETTE_COLOR} transparent opacity={0.45} />
      </mesh>
    );
  }
  if (zoneId === "sky") {
    return (
      <mesh position={[cx, y + 0.5, cz]}>
        <sphereGeometry args={[0.4, 8, 6]} />
        <meshLambertMaterial color={SILHOUETTE_COLOR} transparent opacity={0.45} />
      </mesh>
    );
  }
  // Everywhere else: a ghosted young tree (trunk + canopy), whispering
  // "something could grow here" -- not a rock cone.
  return (
    <group position={[cx, y, cz]}>
      <mesh position={[0, 0.22, 0]}>
        <cylinderGeometry args={[0.05, 0.07, 0.44, 6]} />
        <meshLambertMaterial color={SILHOUETTE_COLOR} transparent opacity={0.5} />
      </mesh>
      <mesh position={[0, 0.78, 0]}>
        <coneGeometry args={[0.3, 0.75, 7]} />
        <meshLambertMaterial color={SILHOUETTE_COLOR} transparent opacity={0.5} />
      </mesh>
    </group>
  );
}
