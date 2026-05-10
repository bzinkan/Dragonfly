import { StyleSheet } from "react-native";

import { Text, View } from "@/components/Themed";
import { env } from "@/src/config/env";

export default function SettingsScreen() {
  return (
    <View style={styles.container}>
      <Text style={styles.title}>Settings</Text>
      <View
        style={styles.separator}
        lightColor="#eee"
        darkColor="rgba(255,255,255,0.1)"
      />
      <Text style={styles.label}>Build</Text>
      <Text style={styles.value}>env: {env.appEnv}</Text>
      <Text style={styles.value}>API: {env.apiBaseUrl}</Text>
      <Text style={styles.value}>updates channel: {env.updatesChannel}</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    alignItems: "flex-start",
    justifyContent: "flex-start",
    padding: 24,
  },
  title: {
    fontSize: 22,
    fontWeight: "600",
  },
  separator: {
    marginVertical: 16,
    height: 1,
    width: "100%",
  },
  label: {
    fontSize: 13,
    fontWeight: "600",
    opacity: 0.7,
    marginTop: 12,
  },
  value: {
    fontSize: 14,
    marginTop: 4,
  },
});
