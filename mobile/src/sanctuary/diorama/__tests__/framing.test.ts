import { SANCTUARY_ZONE_ORDER } from "@/src/api/sanctuary";
import { ISLAND_ART_HALF_WIDTH } from "@/src/sanctuary/diorama/artFit";
import {
  DIVE_FILL_FRACTION,
  diveScaleFor,
  vistaFraming,
  zoneFraming,
} from "@/src/sanctuary/diorama/framing";
import {
  ISLAND_SLOTS,
  REFERENCE_SCREEN_WIDTH,
  VISTA_CANVAS,
} from "@/src/sanctuary/diorama/vistaLayout";

describe("vistaFraming", () => {
  it("centers the canvas at 1:1 zoom", () => {
    expect(vistaFraming()).toEqual({
      x: VISTA_CANVAS.width / 2,
      y: VISTA_CANVAS.height / 2,
      scale: 1,
    });
  });
});

describe("zoneFraming", () => {
  it.each(SANCTUARY_ZONE_ORDER)("returns finite framing for %s", (zoneId) => {
    const framing = zoneFraming(zoneId);
    expect(Number.isFinite(framing.x)).toBe(true);
    expect(Number.isFinite(framing.y)).toBe(true);
    expect(Number.isFinite(framing.scale)).toBe(true);
    expect(framing.scale).toBeGreaterThan(1);
  });

  it.each(SANCTUARY_ZONE_ORDER)("centers the %s island slot", (zoneId) => {
    const framing = zoneFraming(zoneId);
    expect(framing.x).toBe(ISLAND_SLOTS[zoneId].x);
    expect(framing.y).toBe(ISLAND_SLOTS[zoneId].y);
  });

  // D7 dive-fill contract (D4 finding c): the dive zoom is DERIVED so the
  // painted plateau (2 x half-width x islandScale, then x dive scale)
  // always spans DIVE_FILL_FRACTION (~87.5%, Brian's 85-90% direction) of
  // the reference screen -- for every island, regardless of vista size.
  it.each(SANCTUARY_ZONE_ORDER)(
    "dive fills the screen with the %s plateau",
    (zoneId) => {
      const onScreen =
        2 *
        ISLAND_ART_HALF_WIDTH *
        ISLAND_SLOTS[zoneId].islandScale *
        zoneFraming(zoneId).scale;
      expect(onScreen).toBeCloseTo(
        DIVE_FILL_FRACTION * REFERENCE_SCREEN_WIDTH,
        8,
      );
    },
  );

  it("zooms small islands in harder than big ones", () => {
    // elsewhere (islandScale 0.6) needs a much deeper dive than meadow
    // (1.6) to reach the same fill -- the derivation replaces the old
    // hand-tuned DIVE_SCALE_OVERRIDES table.
    expect(diveScaleFor("elsewhere")).toBeGreaterThan(diveScaleFor("meadow"));
    expect(zoneFraming("elsewhere").scale).toBe(diveScaleFor("elsewhere"));
  });
});
