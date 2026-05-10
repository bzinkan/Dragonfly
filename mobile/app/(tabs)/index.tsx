import { useEffect, useState } from "react";
import { ActivityIndicator, StyleSheet } from "react-native";

import { Text, View } from "@/components/Themed";
import { fetchHealth, type HealthResponse } from "@/src/api/health";
import { env } from "@/src/config/env";

type State =
  | { kind: "loading" }
  | { kind: "ok"; body: HealthResponse }
  | { kind: "error"; message: string };

export default function HomeScreen() {
  const [state, setState] = useState<State>({ kind: "loading" });

  useEffect(() => {
    const controller = new AbortController();
    fetchHealth(controller.signal)
      .then((body) => setState({ kind: "ok", body }))
      .catch((err: unknown) => {
        if (controller.signal.aborted) return;
        setState({
          kind: "error",
          message: err instanceof Error ? err.message : String(err),
        });
      });
    return () => controller.abort();
  }, []);

  return (
    <View style={styles.container}>
      <Text style={styles.title}>Dragonfly</Text>
      <Text style={styles.subtitle}>API: {env.apiBaseUrl}</Text>
      <View
        style={styles.separator}
        lightColor="#eee"
        darkColor="rgba(255,255,255,0.1)"
      />
      {state.kind === "loading" && <ActivityIndicator />}
      {state.kind === "ok" && (
        <>
          <Text style={styles.ok}>● {state.body.status}</Text>
          <Text style={styles.meta}>
            env: {state.body.env} · version: {state.body.version}
          </Text>
        </>
      )}
      {state.kind === "error" && (
        <>
          <Text style={styles.error}>● error</Text>
          <Text style={styles.meta}>{state.message}</Text>
        </>
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    alignItems: "center",
    justifyContent: "center",
    padding: 24,
  },
  title: {
    fontSize: 28,
    fontWeight: "bold",
  },
  subtitle: {
    fontSize: 13,
    opacity: 0.6,
    marginTop: 4,
  },
  separator: {
    marginVertical: 24,
    height: 1,
    width: "80%",
  },
  ok: {
    fontSize: 18,
    color: "#22c55e",
  },
  error: {
    fontSize: 18,
    color: "#ef4444",
  },
  meta: {
    fontSize: 13,
    opacity: 0.7,
    marginTop: 6,
    textAlign: "center",
  },
});
