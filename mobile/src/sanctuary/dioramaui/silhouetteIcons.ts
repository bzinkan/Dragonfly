/**
 * Silhouette hints for cued dormant zones. The mystery-cue DTO carries no
 * icon field (title/detail only), so the hint shape is a static authored
 * choice: each zone's most iconic COARSE sprite from the generated
 * manifest, rendered as a dark-translucent silhouette swaying on the
 * dormant island. Completeness against the sprite manifest is unit-tested.
 */

import type { SanctuaryZoneId } from "@/src/api/sanctuary";

/** Zone -> element-sprite key (SANCTUARY_ELEMENT_SPRITES) for its hint. */
export const ZONE_SILHOUETTE_ICON: Record<SanctuaryZoneId, string> = {
  meadow: "sanctuary.meadow.plantae",
  woodland: "sanctuary.woodland.mammalia",
  pond: "sanctuary.pond.amphibia",
  sky: "sanctuary.sky.aves",
  soil: "sanctuary.soil.fungi",
  urban: "sanctuary.urban.aves",
  elsewhere: "sanctuary.elsewhere.unknown",
};
