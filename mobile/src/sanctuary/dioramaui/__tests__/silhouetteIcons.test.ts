import { SANCTUARY_ZONE_ORDER } from "@/src/api/sanctuary";
import { SANCTUARY_ELEMENT_SPRITES } from "@/src/sanctuary/art/sprites.gen";
import { ZONE_SILHOUETTE_ICON } from "@/src/sanctuary/dioramaui/silhouetteIcons";

describe("ZONE_SILHOUETTE_ICON", () => {
  it("names an icon for every zone", () => {
    expect(Object.keys(ZONE_SILHOUETTE_ICON).sort()).toEqual(
      [...SANCTUARY_ZONE_ORDER].sort(),
    );
  });

  it.each(SANCTUARY_ZONE_ORDER)(
    "%s resolves to a real manifest sprite of its own zone",
    (zoneId) => {
      const iconKey = ZONE_SILHOUETTE_ICON[zoneId];
      const sprite = SANCTUARY_ELEMENT_SPRITES[iconKey];
      // A silhouette hint must never fall back to a placeholder shape --
      // the whole point is a recognizable dark outline.
      expect(sprite).toBeDefined();
      expect(sprite.zone).toBe(zoneId);
    },
  );
});
