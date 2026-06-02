import type { ExpoConfig } from "expo/config";

type AppEnv = "development" | "preview" | "production";

const APP_ENV: AppEnv =
  (process.env.APP_ENV as AppEnv | undefined) ?? "development";

type FirebaseConfig = {
  apiKey: string;
  authDomain: string;
  projectId: string;
};

type EntraConfig = {
  clientId: string;
  authority: string;
  redirectUri: string;
};

type EnvConfig = {
  apiBaseUrl: string;
  bundleIdSuffix: string;
  updatesChannel: string;
  firebase: FirebaseConfig;
  entra: EntraConfig;
};

// Firebase Web API keys are public identifiers, not secrets -- access is
// gated by Firebase Auth + Security Rules. Safe to embed in client bundles.
const FIREBASE_DEV: FirebaseConfig = {
  apiKey: "AIzaSyAg2gIzrXoYbeLx5cKWB1QXCZiDWEF2Yh4",
  authDomain: "dragonflyapp-495423.firebaseapp.com",
  projectId: "dragonflyapp-495423",
};

// Entra External Identities customer tenant (CIAM) from Phase 1.
// clientId is the `dragonfly-client` public app registration; authority
// targets the `login.microsoftonline.com/{ciam-tenant-id}/v2.0` flow.
// Public values; access is gated by Entra + pre-authorized scope.
const ENTRA_DEV: EntraConfig = {
  clientId: "6d1b6e1f-42fa-4977-b67f-a15b1f84d4ff",
  authority:
    "https://login.microsoftonline.com/dfd7ebb4-0b29-42cb-aa05-e5e0124bab8f",
  redirectUri: "https://parents.dragonfly-app.net/auth/callback",
};

const ENV: Record<AppEnv, EnvConfig> = {
  development: {
    apiBaseUrl: "https://api.dragonfly-app.net",
    bundleIdSuffix: ".dev",
    updatesChannel: "development",
    firebase: FIREBASE_DEV,
    entra: ENTRA_DEV,
  },
  preview: {
    apiBaseUrl: "https://api.staging.dragonfly-app.net",
    bundleIdSuffix: ".staging",
    updatesChannel: "preview",
    firebase: FIREBASE_DEV,
    entra: ENTRA_DEV,
  },
  production: {
    apiBaseUrl: "https://api.dragonfly-app.net",
    bundleIdSuffix: "",
    updatesChannel: "production",
    firebase: FIREBASE_DEV,
    entra: ENTRA_DEV,
  },
};

const env = ENV[APP_ENV];

const config: ExpoConfig = {
  name: APP_ENV === "production" ? "Dragonfly" : `Dragonfly (${APP_ENV})`,
  slug: "dragonfly",
  version: "0.1.0",
  orientation: "portrait",
  icon: "./assets/images/icon.png",
  scheme: "dragonfly",
  userInterfaceStyle: "automatic",
  newArchEnabled: true,
  splash: {
    image: "./assets/images/splash-icon.png",
    resizeMode: "contain",
    backgroundColor: "#ffffff",
  },
  ios: {
    bundleIdentifier: `com.dragonfly.app${env.bundleIdSuffix}`,
    supportsTablet: true,
  },
  android: {
    package: `com.dragonfly.app${env.bundleIdSuffix}`,
    adaptiveIcon: {
      foregroundImage: "./assets/images/adaptive-icon.png",
      backgroundColor: "#ffffff",
    },
    edgeToEdgeEnabled: true,
    predictiveBackGestureEnabled: false,
  },
  web: {
    bundler: "metro",
    output: "static",
    favicon: "./assets/images/favicon.png",
  },
  plugins: [
    "expo-router",
    "expo-secure-store",
    [
      "expo-camera",
      {
        cameraPermission:
          "Dragonfly uses your camera to take photos of plants and animals you find.",
        recordAudioAndroid: false,
      },
    ],
    [
      "expo-image-picker",
      {
        photosPermission:
          "Dragonfly uses your photo library so you can pick a photo of a plant or animal you found.",
      },
    ],
    [
      "expo-location",
      {
        locationAlwaysAndWhenInUsePermission:
          "Dragonfly uses your location to remember where you spotted each species.",
      },
    ],
  ],
  experiments: {
    typedRoutes: true,
  },
  extra: {
    appEnv: APP_ENV,
    apiBaseUrl: env.apiBaseUrl,
    updatesChannel: env.updatesChannel,
    firebase: env.firebase,
    entra: env.entra,
  },
};

export default config;
