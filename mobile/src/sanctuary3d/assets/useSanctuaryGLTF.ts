/**
 * GLB loading for the Sanctuary 3D diorama.
 *
 * Deliberately NOT drei's useGLTF: the drei/native helpers lean on
 * DOM/Blob APIs that are fragile on Hermes (drei #2493). This loads a
 * Metro-bundled `.glb` asset via expo-asset into an ArrayBuffer and hands
 * it to three's GLTFLoader.parse -- the one path that is known-good on
 * React Native. Never Blob, never fetch(file://), never createObjectURL.
 *
 * Offline invariant (docs/sanctuary.md): assets are bundled with the app;
 * `Asset.downloadAsync()` on a bundled module is a local copy/no-op, not a
 * network fetch.
 */

import { useEffect, useState } from "react";
import { Asset } from "expo-asset";
import { File } from "expo-file-system";
import { GLTFLoader, type GLTF } from "three/examples/jsm/loaders/GLTFLoader.js";

/** Module-level cache: each GLB is parsed once per app session. */
const gltfCache = new Map<number, Promise<GLTF>>();

export function loadGLTFAsset(moduleId: number): Promise<GLTF> {
  let cached = gltfCache.get(moduleId);
  if (!cached) {
    cached = loadUncached(moduleId);
    // A failed load should be retryable on next mount, not poisoned forever.
    cached.catch(() => gltfCache.delete(moduleId));
    gltfCache.set(moduleId, cached);
  }
  return cached;
}

async function loadUncached(moduleId: number): Promise<GLTF> {
  const asset = Asset.fromModule(moduleId);
  if (!asset.localUri) {
    await asset.downloadAsync();
  }
  const uri = asset.localUri ?? asset.uri;
  if (!uri) {
    throw new Error(`sanctuary3d: asset ${asset.name} has no local URI`);
  }
  const bytes = await new File(uri).bytes();
  // Copy into a tight ArrayBuffer in case the view is offset into a pool.
  const buffer = bytes.buffer.slice(
    bytes.byteOffset,
    bytes.byteOffset + bytes.byteLength,
  ) as ArrayBuffer;
  const loader = new GLTFLoader();
  return loader.parseAsync(buffer, "");
}

export type GLTFState =
  | { status: "loading"; gltf: null; error: null }
  | { status: "ready"; gltf: GLTF; error: null }
  | { status: "error"; gltf: null; error: Error };

/**
 * Hook wrapper. `moduleId` is the value of `require("….glb")` -- stable
 * across renders, so it is a safe effect dependency.
 */
export function useSanctuaryGLTF(moduleId: number): GLTFState {
  const [state, setState] = useState<GLTFState>({
    status: "loading",
    gltf: null,
    error: null,
  });

  useEffect(() => {
    let cancelled = false;
    setState({ status: "loading", gltf: null, error: null });
    loadGLTFAsset(moduleId).then(
      (gltf) => {
        if (!cancelled) setState({ status: "ready", gltf, error: null });
      },
      (error: unknown) => {
        if (!cancelled) {
          setState({
            status: "error",
            gltf: null,
            error: error instanceof Error ? error : new Error(String(error)),
          });
        }
      },
    );
    return () => {
      cancelled = true;
    };
  }, [moduleId]);

  return state;
}
