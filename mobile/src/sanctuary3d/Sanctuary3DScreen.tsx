/**
 * Sanctuary 3D living diorama -- screen shell (M1, ADR 0011).
 *
 * M1 scope: season-driven sky/atmosphere + a placeholder island whose seven
 * zones render as tinted patches at their authored layout positions, with
 * locked zones in the dormant grey. The authored island mesh (asset
 * milestone A3), data-driven elements (M2), ambient animation (M3),
 * gestures/inspection (M4), and the reveal sequence (M5) layer on top.
 *
 * Resilience contract (the part that IS final in M1):
 * - Any render error inside the canvas -> GL crash recorded -> this session
 *   falls back to Sanctuary2DScreen in place. Three strikes pin 2D until an
 *   app update (src/sanctuary3d/flagDecision.ts).
 * - Mount watchdog: no first rendered frame within 5 s counts as a crash --
 *   native GL failures can present as a silent hang (expo #41543).
 * - All failure paths land on the permanent 2D screen, never a dead canvas.
 *
 * Inherits every Sanctuary invariant: read-only authored content, no
 * precise location, offline render (bundled assets only), no analytics.
 */

import React, { Component, type ReactNode, useEffect, useRef, useState } from "react";
import { ActivityIndicator, Pressable, StyleSheet, Text, View } from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import { Canvas, useFrame } from "@react-three/fiber/native";

import { SANCTUARY_ZONE_ORDER, type SanctuaryZoneDto } from "@/src/api/sanctuary";
import Sanctuary2DScreen from "@/src/sanctuary/Sanctuary2DScreen";
import { useSanctuary } from "@/src/sanctuary/useSanctuary";
import { ZONE_LAYOUT } from "@/src/sanctuary3d/placement/zoneAnchors";
import { useSanctuary3DPrefs } from "@/src/sanctuary3d/prefs";
import { scenePalette, type ScenePalette } from "@/src/sanctuary3d/season/palette";

const FIRST_FRAME_WATCHDOG_MS = 5_000;

/** Zone ground tints until the authored island + zone palettes land (A3/A8). */
const ZONE_PLACEHOLDER_COLOR: Record<string, string> = {
  meadow: "#8FBC6F",
  woodland: "#528C40",
  pond: "#7FB8C4",
  urban: "#C9CDD1",
  soil: "#6E5235",
  sky: "#F2F5F7",
  elsewhere: "#B5A8C9",
};

/** Dormant grey for zones the kid has not woken yet (asleep, not locked). */
const DORMANT_COLOR = "#84867F";

export default function Sanctuary3DScreen() {
  const { data, isLoading, isError, error, refetch } = useSanctuary();
  const recordGlCrash = useSanctuary3DPrefs((s) => s.recordGlCrash);
  const [sessionFallback, setSessionFallback] = useState(false);

  if (sessionFallback) {
    return <Sanctuary2DScreen />;
  }

  if (isLoading) {
    return (
      <SafeAreaView style={styles.centered} edges={["top"]}>
        <ActivityIndicator />
        <Text style={styles.centeredText}>Waking up…</Text>
      </SafeAreaView>
    );
  }

  if (isError || !data) {
    return (
      <SafeAreaView style={styles.centered} edges={["top"]}>
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
      </SafeAreaView>
    );
  }

  const palette = scenePalette(data.season.season, data.season.background_tone);

  return (
    <GlCrashBoundary
      onCrash={() => {
        recordGlCrash();
        setSessionFallback(true);
      }}
      fallback={<Sanctuary2DScreen />}
    >
      <SafeAreaView style={styles.root} edges={["top"]}>
        <View style={styles.header}>
          <Text style={styles.headerTitle}>Sanctuary</Text>
          <Text style={styles.headerSubtitle}>
            A quiet place that grows when you go outside.
          </Text>
        </View>
        <IslandCanvas
          zones={data.zones}
          palette={palette}
          onMountFailure={() => {
            recordGlCrash();
            setSessionFallback(true);
          }}
        />
      </SafeAreaView>
    </GlCrashBoundary>
  );
}

// ---------------------------------------------------------------------------
// Canvas + watchdog
// ---------------------------------------------------------------------------

function IslandCanvas({
  zones,
  palette,
  onMountFailure,
}: {
  zones: SanctuaryZoneDto[];
  palette: ScenePalette;
  onMountFailure: () => void;
}) {
  const firstFrameSeen = useRef(false);

  useEffect(() => {
    const timer = setTimeout(() => {
      if (!firstFrameSeen.current) {
        onMountFailure();
      }
    }, FIRST_FRAME_WATCHDOG_MS);
    return () => clearTimeout(timer);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return (
    <Canvas
      style={styles.canvas}
      camera={{ position: [0, 6.5, 11], fov: 42 }}
      onCreated={(state) => {
        state.camera.lookAt(0, 0, 0);
        // New-architecture workaround lineage (r3f #3399): expo-gl does not
        // implement UNPACK_FLIP_Y_WEBGL; filter it out of pixelStorei calls.
        const gl = state.gl.getContext() as WebGLRenderingContext & {
          pixelStorei: (pname: number, param: unknown) => void;
        };
        const basePixelStorei = gl.pixelStorei.bind(gl);
        gl.pixelStorei = (pname: number, param: unknown) => {
          if (pname === gl.UNPACK_FLIP_Y_WEBGL) return;
          basePixelStorei(pname, param as number);
        };
      }}
    >
      <FirstFramePing
        onFirstFrame={() => {
          firstFrameSeen.current = true;
        }}
      />
      <color attach="background" args={[palette.sky]} />
      <fog attach="fog" args={[palette.fog, 14, 34]} />
      <hemisphereLight args={[palette.hemiSky, palette.hemiGround, 0.9]} />
      <directionalLight position={[5, 8, 4]} intensity={palette.sunIntensity} />
      <PlaceholderIsland zones={zones} palette={palette} />
    </Canvas>
  );
}

function FirstFramePing({ onFirstFrame }: { onFirstFrame: () => void }) {
  const pinged = useRef(false);
  useFrame(() => {
    if (!pinged.current) {
      pinged.current = true;
      onFirstFrame();
    }
  });
  return null;
}

// ---------------------------------------------------------------------------
// Placeholder island (replaced by the authored mesh in asset milestone A3)
// ---------------------------------------------------------------------------

function PlaceholderIsland({
  zones,
  palette,
}: {
  zones: SanctuaryZoneDto[];
  palette: ScenePalette;
}) {
  const zoneById = new Map(zones.map((z) => [z.zone_id, z] as const));

  return (
    <group>
      {/* Island base: a low cylinder with the season ground tint. */}
      <mesh position={[0, -0.6, 0]}>
        <cylinderGeometry args={[5.6, 4.2, 1.2, 9]} />
        <meshLambertMaterial color={palette.ground} />
      </mesh>
      {/* Underside rock taper so the island reads as floating. */}
      <mesh position={[0, -1.8, 0]}>
        <coneGeometry args={[4.2, 2.4, 9]} />
        <meshLambertMaterial color="#6B5B49" />
      </mesh>
      {SANCTUARY_ZONE_ORDER.map((zoneId) => {
        const layout = ZONE_LAYOUT[zoneId];
        const zone = zoneById.get(zoneId);
        const awake = zone?.unlocked ?? false;
        const color = awake
          ? (ZONE_PLACEHOLDER_COLOR[zoneId] ?? palette.ground)
          : DORMANT_COLOR;
        if (zoneId === "sky") {
          // Sky zone placeholder: a small cloud puff overhead when awake.
          return awake ? (
            <mesh key={zoneId} position={[layout.center[0], layout.center[1], layout.center[2]]}>
              <sphereGeometry args={[0.6, 10, 8]} />
              <meshLambertMaterial color={color} />
            </mesh>
          ) : null;
        }
        if (zoneId === "elsewhere") {
          // Detached floating islet.
          return (
            <group key={zoneId} position={[layout.center[0], layout.center[1], layout.center[2]]}>
              <mesh>
                <cylinderGeometry args={[layout.radius, layout.radius * 0.55, 0.5, 7]} />
                <meshLambertMaterial color={color} />
              </mesh>
            </group>
          );
        }
        if (zoneId === "soil") {
          // Front cliff cross-section: a flat panel on the island face.
          return (
            <mesh
              key={zoneId}
              position={[layout.center[0], layout.center[1], layout.center[2]]}
              rotation={[-0.32, 0, 0]}
            >
              <boxGeometry args={[layout.radius * 2, 1.1, 0.2]} />
              <meshLambertMaterial color={color} />
            </mesh>
          );
        }
        // Ground zones: a slightly raised patch at the zone center.
        return (
          <mesh
            key={zoneId}
            position={[layout.center[0], 0.02, layout.center[2]]}
            rotation={[-Math.PI / 2, 0, 0]}
          >
            <circleGeometry args={[layout.radius, 16]} />
            <meshLambertMaterial color={color} />
          </mesh>
        );
      })}
    </group>
  );
}

// ---------------------------------------------------------------------------
// Crash boundary
// ---------------------------------------------------------------------------

class GlCrashBoundary extends Component<
  { children: ReactNode; fallback: ReactNode; onCrash: () => void },
  { crashed: boolean }
> {
  state = { crashed: false };

  static getDerivedStateFromError() {
    return { crashed: true };
  }

  componentDidCatch(error: unknown) {
    console.error("sanctuary3d: canvas crashed, falling back to 2D", error);
    this.props.onCrash();
  }

  render() {
    return this.state.crashed ? this.props.fallback : this.props.children;
  }
}

// ---------------------------------------------------------------------------
// Styles
// ---------------------------------------------------------------------------

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: "#F7F6F2" },
  canvas: { flex: 1 },
  header: { paddingHorizontal: 16, paddingTop: 8, paddingBottom: 8 },
  headerTitle: { fontSize: 24, fontWeight: "700", color: "#2A2A2A" },
  headerSubtitle: { fontSize: 13, color: "#666", marginTop: 2 },
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
    paddingVertical: 8,
    paddingHorizontal: 16,
    borderRadius: 8,
    backgroundColor: "#3F6B40",
  },
  retryButtonText: { color: "#fff", fontSize: 14, fontWeight: "500" },
});
