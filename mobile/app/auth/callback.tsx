import { Stack } from "expo-router";
import { ActivityIndicator, StyleSheet } from "react-native";

import DesktopContainer from "@/components/DesktopContainer";
import { Text, View } from "@/components/Themed";

/**
 * Static Microsoft redirect target for the parents web surface.
 *
 * RootLayout starts MSAL and consumes the authorization response. MSAL then
 * returns to the page that initiated login. This screen must not inspect,
 * render, log, or clear the query string before handleRedirectPromise() runs.
 */
export default function ParentAuthCallbackScreen() {
  return (
    <DesktopContainer>
      <Stack.Screen options={{ title: "Finishing sign-in" }} />
      <View
        testID="parent-auth-callback"
        accessibilityRole="progressbar"
        style={styles.container}
      >
        <ActivityIndicator size="large" />
        <Text style={styles.title}>Finishing secure sign-in…</Text>
        <Text style={styles.body}>
          Keep this tab open. You will return to parent setup automatically.
        </Text>
      </View>
    </DesktopContainer>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    alignItems: "center",
    justifyContent: "center",
    gap: 14,
    padding: 24,
  },
  title: {
    fontSize: 24,
    fontWeight: "700",
    textAlign: "center",
  },
  body: {
    maxWidth: 480,
    color: "#666",
    fontSize: 16,
    lineHeight: 24,
    textAlign: "center",
  },
});
