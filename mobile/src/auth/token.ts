/**
 * Bearer-token storage for the API client.
 *
 * Phase 6 dev: the token is pasted manually into the Settings tab.
 * Phase 7+ replaces this with the real Firebase Web SDK
 * (signInWithEmailAndPassword for parents, signInWithCustomToken for kids)
 * which writes the same key on token refresh.
 *
 * Web build: SecureStore is no-op on web. Falls back to localStorage so the
 * web preview still works during development.
 */
import * as SecureStore from "expo-secure-store";
import { Platform } from "react-native";

const KEY = "dragonfly.bearer_token";

export async function getBearerToken(): Promise<string | null> {
  if (Platform.OS === "web") {
    return globalThis.localStorage?.getItem(KEY) ?? null;
  }
  return await SecureStore.getItemAsync(KEY);
}

export async function setBearerToken(token: string): Promise<void> {
  if (Platform.OS === "web") {
    globalThis.localStorage?.setItem(KEY, token);
    return;
  }
  await SecureStore.setItemAsync(KEY, token);
}

export async function clearBearerToken(): Promise<void> {
  if (Platform.OS === "web") {
    globalThis.localStorage?.removeItem(KEY);
    return;
  }
  await SecureStore.deleteItemAsync(KEY);
}
