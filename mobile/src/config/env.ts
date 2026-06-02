import Constants from "expo-constants";

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

type Extra = {
  appEnv: "development" | "preview" | "production";
  apiBaseUrl: string;
  updatesChannel: string;
  firebase: FirebaseConfig;
  entra: EntraConfig;
};

const extra = Constants.expoConfig?.extra as Extra | undefined;

if (!extra?.apiBaseUrl) {
  throw new Error(
    "expo config `extra.apiBaseUrl` is missing. Check app.config.ts and APP_ENV.",
  );
}

if (!extra.firebase?.apiKey) {
  throw new Error(
    "expo config `extra.firebase` is missing. Check app.config.ts and APP_ENV.",
  );
}

if (!extra.entra?.clientId) {
  throw new Error(
    "expo config `extra.entra` is missing. Check app.config.ts and APP_ENV.",
  );
}

export const env: Extra = {
  appEnv: extra.appEnv,
  apiBaseUrl: extra.apiBaseUrl,
  updatesChannel: extra.updatesChannel,
  firebase: extra.firebase,
  entra: extra.entra,
};
