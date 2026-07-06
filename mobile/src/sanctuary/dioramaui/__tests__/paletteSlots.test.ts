import { SANCTUARY_ZONE_ORDER } from "@/src/api/sanctuary";
import { SANCTUARY_PALETTE_SLOTS } from "@/src/sanctuary/art/islandLayers.gen";
import { ZONE_ACCENT_COLOR } from "@/src/sanctuary/diorama/scene/zoneColors";
import { scenePalette } from "@/src/sanctuary/diorama/season/palette";
import {
  applyColorMatrixToHex,
  DORMANT_SAT,
  dormantSlotHexes,
  mixHex,
  paletteSlotHexes,
  satMatrix,
  silhouetteSlotHexes,
  zoneAccentSlotHexes,
} from "@/src/sanctuary/dioramaui/paletteSlots";

const SEASONS = ["spring", "summer", "autumn", "winter"] as const;

describe("paletteSlotHexes", () => {
  it.each(SEASONS)("maps every slot to a valid hex for %s", (season) => {
    const hexes = paletteSlotHexes(scenePalette(season, "fresh"));
    for (const slot of SANCTUARY_PALETTE_SLOTS) {
      expect(hexes[slot]).toMatch(/^#[0-9A-Fa-f]{6}$/);
    }
    expect(Object.keys(hexes)).toHaveLength(SANCTUARY_PALETTE_SLOTS.length);
  });

  it("tracks the ScenePalette sources the art header names", () => {
    const palette = scenePalette("autumn", "fading");
    const hexes = paletteSlotHexes(palette);
    expect(hexes.horizon).toBe(palette.horizon);
    expect(hexes.glow).toBe(palette.sunColor);
    expect(hexes.green_mid).toBe(palette.ground);
  });

  it("changes with the season (token remap, not duplicate art)", () => {
    const spring = paletteSlotHexes(scenePalette("spring", "fresh"));
    const winter = paletteSlotHexes(scenePalette("winter", "still"));
    expect(spring.green_mid).not.toBe(winter.green_mid);
    expect(spring.horizon).not.toBe(winter.horizon);
  });
});

describe("satMatrix", () => {
  it("is the exact identity at s = 1", () => {
    expect(satMatrix(1)).toEqual([
      1, 0, 0, 0, 0,
      0, 1, 0, 0, 0,
      0, 0, 1, 0, 0,
      0, 0, 0, 1, 0,
    ]);
  });

  it("is a 4x5 matrix whose color rows stay luminance-preserving", () => {
    const m = satMatrix(0.12);
    expect(m).toHaveLength(20);
    for (const row of [0, 1, 2]) {
      const sum = m[row * 5] + m[row * 5 + 1] + m[row * 5 + 2];
      expect(sum).toBeCloseTo(1, 10);
    }
    // Alpha row untouched.
    expect(m.slice(15)).toEqual([0, 0, 0, 1, 0]);
  });

  it("applies the warm bias only when desaturated", () => {
    const dormant = satMatrix(0.12);
    expect(dormant[4]).toBeGreaterThan(0); // red offset warms
    expect(dormant[14]).toBeLessThan(0); // blue offset cools away
    expect(satMatrix(1)[4]).toBe(0);
  });
});

describe("zoneAccentSlotHexes (dive zone identity, contract 5)", () => {
  const palette = scenePalette("spring", "fresh");

  it.each(SANCTUARY_ZONE_ORDER)(
    "%s dive slots move green_deep to the zone accent",
    (zoneId) => {
      const dive = zoneAccentSlotHexes(palette, zoneId);
      expect(dive.green_deep).toBe(ZONE_ACCENT_COLOR[zoneId]);
    },
  );

  it("only the accent slot differs from the base mapping", () => {
    const base = paletteSlotHexes(palette);
    const dive = zoneAccentSlotHexes(palette, "pond");
    for (const slot of SANCTUARY_PALETTE_SLOTS) {
      if (slot === "green_deep") continue;
      expect(dive[slot]).toBe(base[slot]);
    }
  });

  it("fixes the D4 gap: green_deep is no longer zone-invariant", () => {
    // D4 pinned green_deep to the woodland accent for every island; a
    // meadow dive and a pond dive must now disagree.
    expect(zoneAccentSlotHexes(palette, "meadow").green_deep).not.toBe(
      zoneAccentSlotHexes(palette, "pond").green_deep,
    );
  });
});

describe("hex color math (baked dormant palette)", () => {
  it("identity matrix round-trips a hex exactly", () => {
    expect(applyColorMatrixToHex("#8FBC6F", satMatrix(1))).toBe("#8FBC6F");
  });

  it("mixHex interpolates endpoints", () => {
    expect(mixHex("#000000", "#FFFFFF", 0)).toBe("#000000");
    expect(mixHex("#000000", "#FFFFFF", 1)).toBe("#FFFFFF");
    expect(mixHex("#000000", "#FFFFFF", 0.5)).toBe("#808080");
  });

  it("dormantSlotHexes matches applying satMatrix per slot", () => {
    // The whole point of the baked dormant palette: substituting these
    // hexes must equal drawing the awake art through a satMatrix
    // saveLayer, so the wake lerp starts pixel-equivalent.
    const base = paletteSlotHexes(scenePalette("summer", "warm"));
    const dormant = dormantSlotHexes(base);
    const m = satMatrix(DORMANT_SAT);
    for (const slot of SANCTUARY_PALETTE_SLOTS) {
      expect(dormant[slot]).toBe(applyColorMatrixToHex(base[slot], m));
      expect(dormant[slot]).toMatch(/^#[0-9A-F]{6}$/);
    }
  });

  it("dormant slots crush chroma toward grey", () => {
    const base = paletteSlotHexes(scenePalette("spring", "fresh"));
    const dormant = dormantSlotHexes(base);
    const spread = (hex: string) => {
      const ch = [1, 3, 5].map((i) => parseInt(hex.slice(i, i + 2), 16));
      return Math.max(...ch) - Math.min(...ch);
    };
    // green_mid is a saturated source; its channel spread must collapse.
    expect(spread(dormant.green_mid)).toBeLessThan(
      spread(base.green_mid) * 0.35,
    );
  });

  it("s = 1 leaves every slot untouched", () => {
    const base = paletteSlotHexes(scenePalette("autumn", "fading"));
    expect(dormantSlotHexes(base, 1)).toEqual(base);
  });
});

describe("silhouetteSlotHexes", () => {
  it("collapses every slot to one dark tint (SrcIn via substitution)", () => {
    const base = paletteSlotHexes(scenePalette("winter", "still"));
    const sil = silhouetteSlotHexes(base);
    const tints = new Set(SANCTUARY_PALETTE_SLOTS.map((slot) => sil[slot]));
    expect(tints.size).toBe(1);
    const [tint] = [...tints];
    expect(tint).toMatch(/^#[0-9A-F]{6}$/);
    // Dark: well below mid-grey on every channel.
    for (const i of [1, 3, 5]) {
      expect(parseInt(tint.slice(i, i + 2), 16)).toBeLessThan(0x90);
    }
  });
});
