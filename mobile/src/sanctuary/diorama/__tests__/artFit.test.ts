import {
  ISLAND_ART_HALF_WIDTH,
  LAYER_ART_PX,
  LAYER_BOTTOM_Y,
  LAYER_H,
  LAYER_RECT,
  LAYER_UNITS_PER_PX,
  LAYER_W,
  SCENERY_SCALE_CLASS,
  SPRITE_CLASS_SCALE,
  SPRITE_UNITS_PER_PX,
  spriteScaleMultiplier,
} from "@/src/sanctuary/diorama/artFit";
import { getScenerySprite } from "@/src/sanctuary/diorama/assets/manifest";
import { DRESSING_RULES } from "@/src/sanctuary/diorama/scene/dressing";

describe("layer art geometry", () => {
  it("maps the 512x384 layer art bottom-center onto the anchor", () => {
    expect(LAYER_W).toBeCloseTo(LAYER_ART_PX.width * LAYER_UNITS_PER_PX, 10);
    expect(LAYER_H).toBeCloseTo(LAYER_ART_PX.height * LAYER_UNITS_PER_PX, 10);
    expect(LAYER_RECT.x).toBeCloseTo(-LAYER_W / 2, 10);
    expect(LAYER_RECT.y).toBeCloseTo(LAYER_BOTTOM_Y - LAYER_H, 10);
    expect(LAYER_RECT.width).toBe(LAYER_W);
    expect(LAYER_RECT.height).toBe(LAYER_H);
  });

  it("derives the island hit half-width from the drawn plateau", () => {
    // 512px x 0.24 units/px / 2 = 61.44 units: what hitTest uses as the
    // island tap radius (D4 finding d).
    expect(ISLAND_ART_HALF_WIDTH).toBeCloseTo(61.44, 10);
  });
});

describe("sprite scale hierarchy (D4 finding e)", () => {
  it("classes every dressing-rule scenery key", () => {
    for (const rule of DRESSING_RULES) {
      expect(SCENERY_SCALE_CLASS[rule.key]).toBeDefined();
    }
  });

  it("orders the class multipliers accent < minor < shrub < canopy", () => {
    expect(SPRITE_CLASS_SCALE.accent).toBeLessThan(SPRITE_CLASS_SCALE.minor);
    expect(SPRITE_CLASS_SCALE.minor).toBeLessThan(SPRITE_CLASS_SCALE.shrub);
    expect(SPRITE_CLASS_SCALE.shrub).toBeLessThan(SPRITE_CLASS_SCALE.canopy);
  });

  it("elements and souvenirs keep authored presence", () => {
    expect(spriteScaleMultiplier("element", "anything")).toBe(1);
    expect(spriteScaleMultiplier("souvenir", "anything")).toBe(1);
  });

  it("unknown scenery falls back to canopy so new art is never invisible", () => {
    expect(spriteScaleMultiplier("scenery", "future-asset")).toBe(1);
  });

  it("draws believable relative sizes through the real manifest", () => {
    // Draw width = viewBox.width x manifest scale x class multiplier x
    // SPRITE_UNITS_PER_PX (the render path in islandArt.ts). Flowers must
    // read clearly smaller than bushes, bushes smaller than trees --
    // on-device the flat multipliers made flowers bush-sized (clip-art).
    const drawWidth = (name: string) => {
      const record = getScenerySprite(name);
      if (!record) throw new Error(`missing scenery sprite ${name}`);
      return (
        record.viewBox.width *
        record.scale *
        spriteScaleMultiplier("scenery", name) *
        SPRITE_UNITS_PER_PX
      );
    };
    expect(drawWidth("flower-purple")).toBeLessThan(drawWidth("bush") * 0.6);
    expect(drawWidth("bush")).toBeLessThan(drawWidth("tree-default") * 0.6);
    expect(drawWidth("mushroom-group")).toBeLessThan(drawWidth("bush"));
    expect(drawWidth("rock-small-a")).toBeLessThan(drawWidth("rock-large-a"));
  });
});
