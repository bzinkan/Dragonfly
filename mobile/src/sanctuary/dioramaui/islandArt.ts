/**
 * SkPicture recording for one island (ADR 0012 render contract: record
 * once, replay per frame -- D4 measured 24.5fps live-ImageSVG vs 54.1fps
 * picture replay on a 2-core emulator). Each island yields five pictures
 * (back/base/mid/fore bands + the painter-sorted sprite set) plus an
 * optional silhouette-hint picture for cued dormant zones.
 *
 * Palette handling: colors reach the art ONLY through svgCache.substitute
 * slot hexes, so seasonal, dive-accent, dormant-desaturated, and
 * silhouette looks are all token remaps recorded once -- never a
 * per-frame filter. Re-recording happens exactly when the caller passes
 * different slots (palette/season/zone-accent/dormant change).
 *
 * No React here; the Skia object is injected so the module stays loadable
 * (and its callers testable) without the native module.
 */

import type { SkPicture, SkSVG } from "@shopify/react-native-skia";

import { SANCTUARY_ISLAND_LAYERS } from "@/src/sanctuary/art/islandLayers.gen";
import {
  LAYER_RECT,
  SPRITE_UNITS_PER_PX,
  spriteScaleMultiplier,
} from "@/src/sanctuary/diorama/artFit";
import {
  getScenerySprite,
  resolveElementSprite,
  type SanctuaryElementSprite,
} from "@/src/sanctuary/diorama/assets/manifest";
import { ZONE_ACCENT_COLOR } from "@/src/sanctuary/diorama/scene/zoneColors";
import {
  SPRITE_HALF_EXTENT,
  type IslandPlan,
} from "@/src/sanctuary/diorama/vistaPlan";
import type { SlotHexes, SvgCache } from "@/src/sanctuary/dioramaui/svgCache";
import { ZONE_SILHOUETTE_ICON } from "@/src/sanctuary/dioramaui/silhouetteIcons";

type SkiaModule = typeof import("@shopify/react-native-skia");
export type SkiaApi = SkiaModule["Skia"];

/** Everything the render tree replays for one island. */
export type IslandPictures = {
  back: SkPicture;
  base: SkPicture;
  mid: SkPicture;
  fore: SkPicture;
  sprites: SkPicture;
  /** Cued dormant zones only; drawn above fore with its own sway. */
  silhouette: SkPicture | null;
};

/**
 * Silhouette hints draw larger than a regular sprite (a shape you notice
 * from vista, and a partner to the 28-unit silhouette hit half-extent).
 */
export const SILHOUETTE_DRAW_SCALE = 2;

/** Generous island-local recording cull rect (matches the D4 spike). */
const RECORD_BOUNDS = { x: -250, y: -250, width: 500, height: 500 };

/** Resolve a placed sprite to its generated art record, if it has one. */
function spriteRecordFor(
  sprite: IslandPlan["sprites"][number],
): { cacheKey: string; record: SanctuaryElementSprite } | null {
  if (sprite.kind === "element" && sprite.iconKey !== null) {
    // The plan does not carry element_type (only manifest fallbacks need
    // it); we only draw the sprite branch, so any type works here.
    const res = resolveElementSprite(sprite.iconKey, "coarse");
    return res.kind === "sprite"
      ? { cacheKey: `sprite:${res.spriteKey}`, record: res.sprite }
      : null;
  }
  if (sprite.kind === "scenery") {
    const name = sprite.key.split("#")[0];
    const record = getScenerySprite(name);
    return record ? { cacheKey: `sprite:${name}`, record } : null;
  }
  // Souvenirs render as fallback shapes until D9 assigns their art.
  return null;
}

/** Record all pictures for one island under one palette. */
export function recordIslandPictures(opts: {
  Skia: SkiaApi;
  island: IslandPlan;
  slots: SlotHexes;
  silhouetteSlots: SlotHexes;
  svgCache: SvgCache<SkSVG>;
}): IslandPictures {
  const { Skia, island, slots, silhouetteSlots, svgCache } = opts;
  const bounds = Skia.XYWHRect(
    RECORD_BOUNDS.x,
    RECORD_BOUNDS.y,
    RECORD_BOUNDS.width,
    RECORD_BOUNDS.height,
  );

  const layers = SANCTUARY_ISLAND_LAYERS[island.zoneId];
  const recordLayer = (band: keyof typeof layers): SkPicture => {
    const svg = svgCache.makeSvg(
      `layer:${island.zoneId}:${band}`,
      layers[band].svg,
      slots,
    );
    const rec = Skia.PictureRecorder();
    const canvas = rec.beginRecording(bounds);
    if (svg !== null) {
      canvas.save();
      canvas.translate(LAYER_RECT.x, LAYER_RECT.y);
      canvas.drawSvg(svg, LAYER_RECT.width, LAYER_RECT.height);
      canvas.restore();
    }
    return rec.finishRecordingAsPicture();
  };

  // Sprites: painter order comes from the plan; scale runs through the
  // artFit class multipliers (D4 finding e -- flora accents draw well
  // below canopy masses). Unmapped icon keys degrade to accent-colored
  // fallback circles instead of blanking.
  const spriteRec = Skia.PictureRecorder();
  const spriteCanvas = spriteRec.beginRecording(bounds);
  const fallbackPaint = Skia.Paint();
  fallbackPaint.setColor(Skia.Color(ZONE_ACCENT_COLOR[island.zoneId]));
  for (const s of island.sprites) {
    const resolved = spriteRecordFor(s);
    const classMul = spriteScaleMultiplier(s.kind, s.key.split("#")[0]);
    if (!resolved) {
      const r = SPRITE_HALF_EXTENT * s.scale * classMul;
      spriteCanvas.drawCircle(s.x, s.y - r, r, fallbackPaint);
      continue;
    }
    const { cacheKey, record } = resolved;
    const svg = svgCache.makeSvg(cacheKey, record.svg, slots);
    if (svg === null) continue;
    const drawW =
      record.viewBox.width * record.scale * s.scale * classMul * SPRITE_UNITS_PER_PX;
    const drawH =
      record.viewBox.height * record.scale * s.scale * classMul * SPRITE_UNITS_PER_PX;
    const ax = record.anchor?.x ?? 0.5; // null anchor = bottom-center
    const ay = record.anchor?.y ?? 1;
    spriteCanvas.save();
    spriteCanvas.translate(s.x - drawW * ax, s.y - drawH * ay);
    spriteCanvas.drawSvg(svg, drawW, drawH);
    spriteCanvas.restore();
  }

  // Silhouette hint: the zone's iconic coarse sprite, every slot collapsed
  // to the dark translucent-reading tint (SrcIn-style via substitution).
  let silhouette: SkPicture | null = null;
  if (island.dormant && island.silhouettes.length > 0) {
    const iconKey = ZONE_SILHOUETTE_ICON[island.zoneId];
    const res = resolveElementSprite(iconKey, "coarse");
    if (res.kind === "sprite") {
      const svg = svgCache.makeSvg(
        `silhouette:${res.spriteKey}`,
        res.sprite.svg,
        silhouetteSlots,
      );
      if (svg !== null) {
        const rec = Skia.PictureRecorder();
        const canvas = rec.beginRecording(bounds);
        for (const marker of island.silhouettes) {
          const drawW =
            res.sprite.viewBox.width *
            res.sprite.scale *
            marker.scale *
            SILHOUETTE_DRAW_SCALE *
            SPRITE_UNITS_PER_PX;
          const drawH =
            res.sprite.viewBox.height *
            res.sprite.scale *
            marker.scale *
            SILHOUETTE_DRAW_SCALE *
            SPRITE_UNITS_PER_PX;
          const ax = res.sprite.anchor?.x ?? 0.5;
          const ay = res.sprite.anchor?.y ?? 1;
          canvas.save();
          canvas.translate(marker.x - drawW * ax, marker.y - drawH * ay);
          canvas.drawSvg(svg, drawW, drawH);
          canvas.restore();
        }
        silhouette = rec.finishRecordingAsPicture();
      }
    }
  }

  return {
    back: recordLayer("back"),
    base: recordLayer("base"),
    mid: recordLayer("mid"),
    fore: recordLayer("fore"),
    sprites: spriteRec.finishRecordingAsPicture(),
    silhouette,
  };
}
