/**
 * Sky + atmosphere for the diorama: a vertical gradient dome drawn in
 * screen space with the near-static sky parallax (PARALLAX_FACTOR.sky),
 * oversized so the slow drift never exposes an edge -- the D4 spike
 * pattern, driven by the ScenePalette so seasons re-tint it for free.
 */

import { useDerivedValue, type SharedValue } from "react-native-reanimated";
import type { Transforms3d } from "@shopify/react-native-skia";

import type { ScenePalette } from "@/src/sanctuary/diorama/season/palette";
import { PARALLAX_FACTOR } from "@/src/sanctuary/diorama/vistaLayout";

type SkiaModule = typeof import("@shopify/react-native-skia");

export function SkyLayer({
  skia,
  palette,
  w,
  h,
  panX,
  baseScale,
}: {
  skia: SkiaModule;
  palette: ScenePalette;
  w: number;
  h: number;
  panX: SharedValue<number>;
  baseScale: number;
}) {
  const { Group, LinearGradient, Rect, vec } = skia;
  const skyTransform = useDerivedValue<Transforms3d>(() => [
    { translateX: -panX.value * PARALLAX_FACTOR.sky * baseScale },
  ]);
  return (
    <Group transform={skyTransform}>
      <Rect x={-w * 0.6} y={0} width={w * 2.2} height={h}>
        <LinearGradient
          start={vec(0, 0)}
          end={vec(0, h)}
          colors={[palette.skyTop, palette.horizon]}
        />
      </Rect>
    </Group>
  );
}

/**
 * A translucent fog band drawn between parallax rows in CANVAS space (the
 * caller places it inside the viewport group): far islands sink into
 * haze, near islands pop -- the 2.5D depth cue. Plain gradient rect, no
 * saveLayer, static per season.
 */
export function HazeBand({
  skia,
  y,
  height,
  color,
  peakAlphaHex,
  canvasWidth,
}: {
  skia: SkiaModule;
  y: number;
  height: number;
  /** ScenePalette.fog hex. */
  color: string;
  /** Two-digit hex alpha at the band's core (e.g. "55"). */
  peakAlphaHex: string;
  canvasWidth: number;
}) {
  const { LinearGradient, Rect, vec } = skia;
  return (
    <Rect x={-300} y={y} width={canvasWidth + 600} height={height}>
      <LinearGradient
        start={vec(0, y)}
        end={vec(0, y + height)}
        colors={[`${color}00`, `${color}${peakAlphaHex}`, `${color}00`]}
      />
    </Rect>
  );
}
