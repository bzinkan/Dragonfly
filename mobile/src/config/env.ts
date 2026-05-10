import Constants from "expo-constants";

type Extra = {
  appEnv: "development" | "preview" | "production";
  apiBaseUrl: string;
  updatesChannel: string;
};

const extra = Constants.expoConfig?.extra as Extra | undefined;

if (!extra?.apiBaseUrl) {
  throw new Error(
    "expo config `extra.apiBaseUrl` is missing. Check app.config.ts and APP_ENV.",
  );
}

export const env: Extra = {
  appEnv: extra.appEnv,
  apiBaseUrl: extra.apiBaseUrl,
  updatesChannel: extra.updatesChannel,
};
