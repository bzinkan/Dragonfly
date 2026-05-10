import { StyleSheet } from "react-native";

import { Text, View } from "@/components/Themed";

type Props = {
  title: string;
  body?: string;
};

export default function PlaceholderScreen({ title, body }: Props) {
  return (
    <View style={styles.container}>
      <Text style={styles.title}>{title}</Text>
      <Text style={styles.body}>
        {body ?? "Coming in a later phase."}
      </Text>
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
    fontSize: 22,
    fontWeight: "600",
  },
  body: {
    marginTop: 8,
    fontSize: 14,
    opacity: 0.6,
  },
});
