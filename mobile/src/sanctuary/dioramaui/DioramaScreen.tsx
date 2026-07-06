/**
 * Sanctuary diorama screen (D7). Owns everything AROUND the canvas:
 *  - the guarded Skia require (a dev client predating the native rebuild
 *    quietly gets the classic screen, never a crash),
 *  - the real data path: useSanctuary -> SanctuarySnapshotDto, with
 *    loading and error states (no sample snapshots),
 *  - the render watchdog: 3-strike crash latch + first-frame timeout with
 *    the same semantics as the 3D latch. The canvas subtree sits inside an
 *    error boundary; a crash OR a canvas that never draws within the
 *    timeout records ONE persisted strike (prefs.recordRenderCrash) and
 *    swaps this session to Sanctuary2DScreen. At MAX_RENDER_CRASHES the
 *    tab route pins to the classic screen across launches.
 *
 * The tab route (app/(tabs)/sanctuary.tsx) only mounts this component
 * when decideSanctuaryDiorama says diorama.
 */

import { useCallback, useEffect, useRef, useState } from "react";
import {
  ActivityIndicator,
  Pressable,
  StyleSheet,
  Text,
  View,
  type LayoutChangeEvent,
} from "react-native";

import { useSanctuaryDioramaPrefs } from "@/src/sanctuary/diorama/prefs";
import { DioramaScene } from "@/src/sanctuary/dioramaui/DioramaScene";
import { RenderBoundary } from "@/src/sanctuary/dioramaui/RenderBoundary";
import {
  FIRST_FRAME_TIMEOUT_MS,
  isStrikeTransition,
  reduceWatchdog,
  type WatchdogEvent,
  type WatchdogPhase,
} from "@/src/sanctuary/dioramaui/watchdog";
import { Sanctuary2DScreen } from "@/src/sanctuary/Sanctuary2DScreen";
import { useSanctuary } from "@/src/sanctuary/useSanctuary";

type SkiaModule = typeof import("@shopify/react-native-skia");

export function DioramaScreen() {
  let skia: SkiaModule | null = null;
  try {
    // eslint-disable-next-line @typescript-eslint/no-var-requires
    skia = require("@shopify/react-native-skia");
  } catch {
    skia = null;
  }

  if (skia === null) {
    // Known state, not a crash: no strike, just the permanent fallback.
    return <Sanctuary2DScreen />;
  }

  return <DioramaGate skia={skia} />;
}

function DioramaGate({ skia }: { skia: SkiaModule }) {
  const { data, isLoading, isError, error, refetch } = useSanctuary();
  const recordRenderCrash = useSanctuaryDioramaPrefs((s) => s.recordRenderCrash);

  // Watchdog: pure reducer behind refs; one strike max per mount.
  const phaseRef = useRef<WatchdogPhase>("waiting");
  const [struck, setStruck] = useState(false);
  const applyEvent = useCallback(
    (event: WatchdogEvent) => {
      const prev = phaseRef.current;
      const next = reduceWatchdog(prev, event);
      phaseRef.current = next;
      if (isStrikeTransition(prev, next)) {
        recordRenderCrash();
        setStruck(true);
      }
    },
    [recordRenderCrash],
  );

  // Arm only while the canvas subtree is actually the rendered branch:
  // a failed refetch keeps cached data (isError && data defined), but the
  // render below shows the Retry screen then — a first-frame timeout in
  // that state would mis-attribute a network condition as a renderer
  // strike and (at three) permanently pin the kid to the classic screen.
  const canvasMounted = !struck && data !== undefined && !isError && !isLoading;
  useEffect(() => {
    if (!canvasMounted) return;
    const timer = setTimeout(
      () => applyEvent("timeout"),
      FIRST_FRAME_TIMEOUT_MS,
    );
    return () => clearTimeout(timer);
  }, [canvasMounted, applyEvent]);

  const onFirstFrame = useCallback(() => applyEvent("first-frame"), [applyEvent]);
  const onCrash = useCallback(() => applyEvent("crash"), [applyEvent]);

  if (struck) {
    // This session falls back immediately; the persisted count decides
    // whether future launches try the diorama again.
    return <Sanctuary2DScreen />;
  }

  if (isLoading) {
    return (
      <View style={styles.centered}>
        <ActivityIndicator />
        <Text style={styles.centeredText}>Waking up…</Text>
      </View>
    );
  }

  if (isError || data === undefined) {
    return (
      <View style={styles.centered}>
        <Text style={styles.centeredTitle}>Couldn't reach your Sanctuary</Text>
        <Text style={styles.centeredText}>
          {error?.message ?? "Try again in a moment."}
        </Text>
        <Pressable
          accessibilityRole="button"
          style={styles.retryButton}
          onPress={() => void refetch()}
        >
          <Text style={styles.retryButtonText}>Retry</Text>
        </Pressable>
      </View>
    );
  }

  return (
    <RenderBoundary onCrash={onCrash}>
      <DioramaBody skia={skia} snapshot={data} onFirstFrame={onFirstFrame} />
    </RenderBoundary>
  );
}

/** First layout wins: the camera initializes from it, and the diorama
 * does not chase rotation/resize (same policy as the D4 spike). */
function DioramaBody({
  skia,
  snapshot,
  onFirstFrame,
}: {
  skia: SkiaModule;
  snapshot: Parameters<typeof DioramaScene>[0]["snapshot"];
  onFirstFrame: () => void;
}) {
  const [size, setSize] = useState<{ w: number; h: number } | null>(null);
  const onLayout = useCallback((e: LayoutChangeEvent) => {
    const { width, height } = e.nativeEvent.layout;
    setSize((prev) => prev ?? (width > 0 && height > 0 ? { w: width, h: height } : prev));
  }, []);

  return (
    <View style={styles.root} onLayout={onLayout}>
      {size ? (
        <DioramaScene
          skia={skia}
          w={size.w}
          h={size.h}
          snapshot={snapshot}
          onFirstFrame={onFirstFrame}
        />
      ) : null}
    </View>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: "#0B0F0D" },
  centered: {
    flex: 1,
    alignItems: "center",
    justifyContent: "center",
    padding: 24,
    backgroundColor: "#F7F6F2",
  },
  centeredTitle: { fontSize: 18, fontWeight: "600", marginBottom: 8 },
  centeredText: { fontSize: 14, color: "#666", marginTop: 8 },
  retryButton: {
    marginTop: 16,
    minHeight: 44,
    minWidth: 44,
    paddingVertical: 8,
    paddingHorizontal: 16,
    borderRadius: 8,
    backgroundColor: "#3F6B40",
    alignItems: "center",
    justifyContent: "center",
  },
  retryButtonText: { color: "#fff", fontSize: 14, fontWeight: "500" },
});
