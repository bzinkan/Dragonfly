import { SANCTUARY_ZONE_ORDER } from "@/src/api/sanctuary";
import { ISLAND_ART_HALF_WIDTH } from "@/src/sanctuary/diorama/artFit";
import {
  ISLAND_SLOTS,
  PARALLAX_FACTOR,
  parallaxFor,
  REFERENCE_SCREEN_WIDTH,
  VISTA_CANVAS,
  VISTA_PAN_LIMIT,
} from "@/src/sanctuary/diorama/vistaLayout";

describe("vista layout", () => {
  it("defines a slot for all 7 zones", () => {
    expect(Object.keys(ISLAND_SLOTS).sort()).toEqual(
      [...SANCTUARY_ZONE_ORDER].sort(),
    );
  });

  it("is a 2.5-screen-wide canvas in 390dp reference units", () => {
    expect(VISTA_CANVAS.width).toBe(2.5 * REFERENCE_SCREEN_WIDTH);
    expect(VISTA_CANVAS.height).toBe(2 * REFERENCE_SCREEN_WIDTH);
  });

  it("clamps the pan at 0.4 reference screens either side", () => {
    expect(VISTA_PAN_LIMIT).toBe(0.4 * REFERENCE_SCREEN_WIDTH);
  });

  it.each(SANCTUARY_ZONE_ORDER)("keeps the %s slot on the canvas", (zoneId) => {
    const slot = ISLAND_SLOTS[zoneId];
    expect(slot.x).toBeGreaterThanOrEqual(0);
    expect(slot.x).toBeLessThanOrEqual(VISTA_CANVAS.width);
    expect(slot.y).toBeGreaterThanOrEqual(0);
    expect(slot.y).toBeLessThanOrEqual(VISTA_CANVAS.height);
    expect(slot.islandScale).toBeGreaterThan(0);
  });

  it.each(SANCTUARY_ZONE_ORDER)("gives %s a valid band", (zoneId) => {
    expect(["back", "mid", "fore"]).toContain(ISLAND_SLOTS[zoneId].band);
  });

  // D4 finding c: with the original slots, woodland (x 180, back band) and
  // elsewhere (x 70) could NEVER enter the viewport -- a back-band anchor
  // only shows when |x - 487.5| <= 195 + panLimit * parallax. This is the
  // reachability contract: the visible window is one reference screen
  // centered on the canvas, slid by the clamped pan times the band's
  // parallax factor, and every island's anchor must fall inside it for
  // some legal pan.
  it.each(SANCTUARY_ZONE_ORDER)(
    "keeps the %s anchor reachable within the pan clamp",
    (zoneId) => {
      const slot = ISLAND_SLOTS[zoneId];
      const reach =
        REFERENCE_SCREEN_WIDTH / 2 + VISTA_PAN_LIMIT * parallaxFor(zoneId);
      expect(Math.abs(slot.x - VISTA_CANVAS.width / 2)).toBeLessThanOrEqual(
        reach,
      );
    },
  );

  // Art direction (D7): islands with real screen presence. The painted
  // plateau is 2 x ISLAND_ART_HALF_WIDTH x islandScale canvas units wide;
  // fore islands must span at least 40% of the reference screen, and even
  // the far islet must not drop under 18%.
  it.each(SANCTUARY_ZONE_ORDER)("gives %s real screen presence", (zoneId) => {
    const slot = ISLAND_SLOTS[zoneId];
    const plateauFraction =
      (2 * ISLAND_ART_HALF_WIDTH * slot.islandScale) / REFERENCE_SCREEN_WIDTH;
    expect(plateauFraction).toBeGreaterThanOrEqual(
      slot.band === "fore" ? 0.4 : 0.18,
    );
  });

  // Staggered depth: at least one pair of fore islands overlaps
  // horizontally at different heights, so the vista reads as occluding
  // 2.5D rows rather than islands floating in isolation.
  it("staggers fore islands with horizontal overlap", () => {
    const fore = SANCTUARY_ZONE_ORDER.map((z) => ISLAND_SLOTS[z]).filter(
      (s) => s.band === "fore",
    );
    let overlaps = 0;
    for (let i = 0; i < fore.length; i++) {
      for (let j = i + 1; j < fore.length; j++) {
        const a = fore[i];
        const b = fore[j];
        const halfA = ISLAND_ART_HALF_WIDTH * a.islandScale;
        const halfB = ISLAND_ART_HALF_WIDTH * b.islandScale;
        if (Math.abs(a.x - b.x) < halfA + halfB && a.y !== b.y) overlaps++;
      }
    }
    expect(overlaps).toBeGreaterThanOrEqual(1);
  });

  it("composes the archipelago per the plan", () => {
    expect(ISLAND_SLOTS.meadow.band).toBe("fore");
    expect(ISLAND_SLOTS.woodland.band).toBe("back");
    expect(ISLAND_SLOTS.pond.band).toBe("fore");
    expect(ISLAND_SLOTS.sky.band).toBe("mid");
    expect(ISLAND_SLOTS.soil.band).toBe("fore");
    expect(ISLAND_SLOTS.urban.band).toBe("mid");
    expect(ISLAND_SLOTS.elsewhere.band).toBe("back");
    // Elsewhere is the small far islet.
    expect(ISLAND_SLOTS.elsewhere.islandScale).toBeLessThan(
      ISLAND_SLOTS.meadow.islandScale,
    );
    // The fore row is the big one: every fore island out-scales every
    // back island (depth = size in a 2.5D vista).
    for (const foreZone of ["meadow", "pond", "soil"] as const) {
      for (const backZone of ["woodland", "elsewhere"] as const) {
        expect(ISLAND_SLOTS[foreZone].islandScale).toBeGreaterThan(
          ISLAND_SLOTS[backZone].islandScale,
        );
      }
    }
  });

  it("parallax factors match the authored bands", () => {
    expect(PARALLAX_FACTOR.back).toBe(0.35);
    expect(PARALLAX_FACTOR.mid).toBe(0.7);
    expect(PARALLAX_FACTOR.fore).toBe(1.0);
    expect(PARALLAX_FACTOR.sky).toBe(0.1);
  });

  it("parallaxFor follows the band except for the sky island", () => {
    expect(parallaxFor("meadow")).toBe(1.0);
    expect(parallaxFor("woodland")).toBe(0.35);
    expect(parallaxFor("urban")).toBe(0.7);
    expect(parallaxFor("sky")).toBe(0.1);
  });
});
