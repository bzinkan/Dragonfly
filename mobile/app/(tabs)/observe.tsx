import { CameraView, useCameraPermissions } from "expo-camera";
import * as ImageManipulator from "expo-image-manipulator";
import { useFocusEffect, useIsFocused } from "@react-navigation/native";
import { router } from "expo-router";
import { useCallback, useRef, useState } from "react";
import {
  ActivityIndicator,
  Alert,
  GestureResponderEvent,
  Image,
  Pressable,
  StyleSheet,
} from "react-native";

import { Text, View } from "@/components/Themed";
import { useDraftStore } from "@/src/observation/draftStore";

const MAX_EDGE_PX = 1600;
const JPEG_QUALITY = 0.8;
const MIN_CAMERA_ZOOM = 0;
const MAX_CAMERA_ZOOM = 0.8;
const PINCH_ZOOM_SENSITIVITY = 0.25;
const CAMERA_RESTART_DELAY_MS = 180;

type Captured = {
  uri: string;
  width: number;
  height: number;
};

function clampZoom(value: number) {
  return Math.min(MAX_CAMERA_ZOOM, Math.max(MIN_CAMERA_ZOOM, value));
}

function formatZoom(value: number) {
  return `${(1 + value * 4).toFixed(1)}x`;
}

function touchDistance(event: GestureResponderEvent) {
  const touches = event.nativeEvent.touches;
  if (touches.length < 2) return null;

  const [first, second] = touches;
  return Math.hypot(first.pageX - second.pageX, first.pageY - second.pageY);
}

export default function ObserveScreen() {
  const [permission, requestPermission] = useCameraPermissions();
  const isFocused = useIsFocused();
  const cameraRef = useRef<CameraView>(null);
  const zoomRef = useRef(0);
  const pinchStartDistanceRef = useRef<number | null>(null);
  const pinchStartZoomRef = useRef(0);
  const [busy, setBusy] = useState(false);
  const [preview, setPreview] = useState<Captured | null>(null);
  const [cameraMounted, setCameraMounted] = useState(false);
  const [cameraSession, setCameraSession] = useState(0);
  const [zoom, setZoom] = useState(0);
  const setDraftPhoto = useDraftStore((s) => s.setPhoto);

  const setCameraZoom = useCallback((value: number) => {
    const next = clampZoom(value);
    zoomRef.current = next;
    setZoom(next);
  }, []);

  const resetPinch = useCallback(() => {
    pinchStartDistanceRef.current = null;
    pinchStartZoomRef.current = zoomRef.current;
  }, []);

  const updatePinchZoom = useCallback(
    (event: GestureResponderEvent) => {
      const distance = touchDistance(event);
      if (distance === null) {
        resetPinch();
        return;
      }

      if (pinchStartDistanceRef.current === null) {
        pinchStartDistanceRef.current = distance;
        pinchStartZoomRef.current = zoomRef.current;
        return;
      }

      const safeScale = Math.max(
        distance / pinchStartDistanceRef.current,
        0.01,
      );
      setCameraZoom(
        pinchStartZoomRef.current +
          Math.log2(safeScale) * PINCH_ZOOM_SENSITIVITY,
      );
    },
    [resetPinch, setCameraZoom],
  );

  useFocusEffect(
    useCallback(() => {
      let cancelled = false;
      setBusy(false);
      setPreview(null);
      setCameraZoom(0);
      resetPinch();
      setCameraMounted(false);
      const restartTimer = setTimeout(() => {
        if (cancelled) return;
        setCameraSession((session) => session + 1);
        setCameraMounted(true);
      }, CAMERA_RESTART_DELAY_MS);

      return () => {
        cancelled = true;
        clearTimeout(restartTimer);
        setCameraMounted(false);
        setBusy(false);
        setPreview(null);
        setCameraZoom(0);
        resetPinch();
      };
    }, [resetPinch, setCameraZoom]),
  );

  if (!permission) {
    return (
      <View style={styles.center}>
        <ActivityIndicator />
      </View>
    );
  }

  if (!permission.granted) {
    return (
      <View style={styles.center}>
        <Text style={styles.heading}>Camera access</Text>
        <Text style={styles.body}>
          Hinterland uses your camera to take photos of plants and animals you
          find.
        </Text>
        <Pressable
          style={[styles.button, styles.buttonPrimary]}
          onPress={() => void requestPermission()}
        >
          <Text style={styles.buttonText}>
            {permission.canAskAgain ? "Allow camera" : "Open settings"}
          </Text>
        </Pressable>
      </View>
    );
  }

  if (preview) {
    return (
      <View style={styles.previewContainer}>
        <Image
          source={{ uri: preview.uri }}
          style={styles.previewImage}
          resizeMode="contain"
        />
        <Text style={styles.previewMeta}>
          {preview.width} × {preview.height}px
        </Text>
        <View style={styles.row}>
          <Pressable
            style={[styles.button, styles.buttonGhost]}
            onPress={() => setPreview(null)}
          >
            <Text style={styles.buttonText}>Retake</Text>
          </Pressable>
          <Pressable
            style={[styles.button, styles.buttonPrimary]}
            onPress={() => {
              setDraftPhoto({
                localUri: preview.uri,
                width: preview.width,
                height: preview.height,
              });
              setPreview(null);
              router.push("/observe-submit");
            }}
          >
            <Text style={styles.buttonText}>Use photo</Text>
          </Pressable>
        </View>
      </View>
    );
  }

  const cameraActive = isFocused && cameraMounted;

  return (
    <View style={styles.container}>
      {cameraActive ? (
        <CameraView
          key={cameraSession}
          ref={cameraRef}
          style={styles.camera}
          facing="back"
          zoom={zoom}
        />
      ) : (
        <View style={[styles.camera, styles.cameraPlaceholder]}>
          <ActivityIndicator color="#fff" />
        </View>
      )}
      {cameraActive ? (
        <View
          style={styles.cameraTouchLayer}
          onStartShouldSetResponder={(event) =>
            event.nativeEvent.touches.length >= 2
          }
          onMoveShouldSetResponder={(event) =>
            event.nativeEvent.touches.length >= 2
          }
          onResponderGrant={updatePinchZoom}
          onResponderMove={updatePinchZoom}
          onResponderRelease={resetPinch}
          onResponderTerminate={resetPinch}
        />
      ) : null}
      {cameraActive ? (
        <Pressable
          hitSlop={12}
          style={styles.zoomBadge}
          onPress={() => setCameraZoom(0)}
        >
          <Text style={styles.zoomBadgeText}>{formatZoom(zoom)}</Text>
        </Pressable>
      ) : null}
      <Pressable
        style={[styles.shutter, (busy || !cameraActive) && styles.shutterBusy]}
        disabled={busy || !cameraActive}
        onPress={async () => {
          if (!cameraRef.current) return;
          setBusy(true);
          try {
            const shot = await cameraRef.current.takePictureAsync({
              quality: 1,
              skipProcessing: false,
            });
            if (!shot) return;
            const longEdge = Math.max(shot.width, shot.height);
            const resize =
              longEdge > MAX_EDGE_PX
                ? shot.width >= shot.height
                  ? { width: MAX_EDGE_PX }
                  : { height: MAX_EDGE_PX }
                : undefined;
            const out = await ImageManipulator.manipulateAsync(
              shot.uri,
              resize ? [{ resize }] : [],
              {
                compress: JPEG_QUALITY,
                format: ImageManipulator.SaveFormat.JPEG,
              },
            );
            setPreview({ uri: out.uri, width: out.width, height: out.height });
          } catch (err) {
            Alert.alert("Capture failed", String(err));
          } finally {
            setBusy(false);
          }
        }}
      >
        {busy ? (
          <ActivityIndicator color="#000" />
        ) : (
          <View style={styles.shutterInner} />
        )}
      </Pressable>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: "#000",
  },
  camera: {
    flex: 1,
  },
  cameraPlaceholder: {
    alignItems: "center",
    justifyContent: "center",
  },
  cameraTouchLayer: {
    ...StyleSheet.absoluteFillObject,
  },
  center: {
    flex: 1,
    alignItems: "center",
    justifyContent: "center",
    padding: 24,
  },
  heading: {
    fontSize: 22,
    fontWeight: "600",
    marginBottom: 8,
  },
  body: {
    fontSize: 14,
    opacity: 0.7,
    textAlign: "center",
    marginBottom: 16,
  },
  shutter: {
    position: "absolute",
    bottom: 40,
    alignSelf: "center",
    width: 72,
    height: 72,
    borderRadius: 36,
    backgroundColor: "#fff",
    alignItems: "center",
    justifyContent: "center",
  },
  shutterBusy: {
    opacity: 0.6,
  },
  zoomBadge: {
    position: "absolute",
    bottom: 130,
    alignSelf: "center",
    minWidth: 58,
    paddingHorizontal: 12,
    paddingVertical: 7,
    borderRadius: 999,
    backgroundColor: "rgba(0, 0, 0, 0.56)",
    borderColor: "rgba(255, 255, 255, 0.32)",
    borderWidth: StyleSheet.hairlineWidth,
    alignItems: "center",
  },
  zoomBadgeText: {
    color: "#fff",
    fontSize: 13,
    fontWeight: "700",
  },
  shutterInner: {
    width: 56,
    height: 56,
    borderRadius: 28,
    backgroundColor: "#fff",
    borderWidth: 3,
    borderColor: "#000",
  },
  previewContainer: {
    flex: 1,
    alignItems: "center",
    padding: 16,
  },
  previewImage: {
    flex: 1,
    width: "100%",
    marginBottom: 12,
  },
  previewMeta: {
    fontSize: 12,
    opacity: 0.6,
    marginBottom: 12,
  },
  row: {
    flexDirection: "row",
    gap: 12,
  },
  button: {
    paddingHorizontal: 18,
    paddingVertical: 10,
    borderRadius: 6,
  },
  buttonPrimary: {
    backgroundColor: "#2f6feb",
  },
  buttonGhost: {
    borderColor: "#888",
    borderWidth: StyleSheet.hairlineWidth,
  },
  buttonText: {
    fontSize: 14,
    color: "#fff",
  },
});
