import FontAwesome from "@expo/vector-icons/FontAwesome";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { router } from "expo-router";
import type { ComponentProps } from "react";
import { useState } from "react";
import {
  ActivityIndicator,
  Alert,
  FlatList,
  Pressable,
  RefreshControl,
  StyleSheet,
} from "react-native";

import { Text, View } from "@/components/Themed";
import { ApiError } from "@/src/api/client";
import {
  type ExpeditionRelevance,
  type ExpeditionSummary,
  type ProgressItem,
  focusExpedition,
  listAvailableExpeditions,
  listMyExpeditions,
  startExpedition,
} from "@/src/api/expeditions";
import {
  activeProgress,
  filterByEnvironment,
  nextObjective,
  progressLabel,
  splitProgress,
} from "@/src/expeditions/logic";
import { useCoarseGeohash } from "@/src/expeditions/useCoarseGeohash";

const STARTER_ID = "backyard_starter";

const ENVIRONMENT_CHIPS: { label: string; value: string | null }[] = [
  { label: "All", value: null },
  { label: "Yard", value: "yard" },
  { label: "Park", value: "park" },
  { label: "Street", value: "street" },
  { label: "School", value: "school" },
];

export default function ExpeditionsScreen() {
  const queryClient = useQueryClient();
  const [env, setEnv] = useState<string | null>(null);
  const geohash = useCoarseGeohash();

  const available = useQuery({
    queryKey: ["expeditions", "available", geohash ?? "none"],
    queryFn: () => listAvailableExpeditions(geohash),
    placeholderData: (prev) => prev,
  });
  const mine = useQuery({
    queryKey: ["expeditions", "me"],
    queryFn: listMyExpeditions,
  });

  const start = useMutation({
    mutationFn: startExpedition,
    onSuccess: (data) => {
      void queryClient.invalidateQueries({ queryKey: ["expeditions"] });
      router.push(`/expedition/${data.expedition_id}`);
    },
    onError: (err) => {
      const message =
        err instanceof ApiError ? `${err.status}: ${err.message}` : String(err);
      Alert.alert("Couldn't start", message);
    },
  });

  const focus = useMutation({
    mutationFn: focusExpedition,
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["expeditions"] });
    },
    onError: (err) => {
      const message =
        err instanceof ApiError ? `${err.status}: ${err.message}` : String(err);
      Alert.alert("Couldn't focus", message);
    },
  });

  if (available.isPending || mine.isPending) {
    return (
      <View style={styles.center}>
        <ActivityIndicator />
      </View>
    );
  }

  const loadError = available.error ?? mine.error;
  if (loadError) {
    const isUnauthed = loadError instanceof ApiError && loadError.status === 401;
    return (
      <View style={styles.center}>
        <FontAwesome name="map-signs" size={28} color="#5fbf8f" />
        <Text style={styles.emptyTitle}>
          {isUnauthed ? "Quest board is waiting" : "Couldn't load quests"}
        </Text>
        <Text style={styles.emptyText}>
          {isUnauthed
            ? "Your expeditions will appear here once this dev build has a session."
            : loadError instanceof Error
              ? loadError.message
              : String(loadError)}
        </Text>
        <Pressable
          style={[styles.button, styles.buttonGhost]}
          onPress={() => {
            void available.refetch();
            void mine.refetch();
          }}
        >
          <Text style={styles.buttonText}>Retry</Text>
        </Pressable>
      </View>
    );
  }

  const progressItems = mine.data?.items ?? [];
  const { inProgress, completed } = splitProgress(progressItems);
  const active = activeProgress(progressItems, mine.data?.active_expedition_id);
  const allAvailable = available.data?.items ?? [];
  const starter =
    progressItems.length === 0
      ? allAvailable.find((item) => item.id === STARTER_ID) ?? null
      : null;
  const items = filterByEnvironment(allAvailable, env).filter(
    (item) => item.id !== starter?.id,
  );

  return (
    <FlatList
      data={items}
      keyExtractor={(item) => item.id}
      contentContainerStyle={styles.list}
      ListHeaderComponent={
        <View style={styles.section}>
          <Text style={styles.kicker}>Expeditions</Text>
          <Text style={styles.title}>Choose a field quest</Text>
          <Text style={styles.subtitle}>
            Every photo is a move. Match the objective, advance the quest.
          </Text>

          {active ? (
            <ActiveMission item={active} />
          ) : starter ? (
            <StarterMission
              item={starter}
              onStart={() => start.mutate(starter.id)}
              starting={start.isPending && start.variables === starter.id}
            />
          ) : (
            <View style={styles.emptyPanel}>
              <Text style={styles.emptyTitle}>No active quest</Text>
              <Text style={styles.emptyText}>
                Pick an expedition below to start a mission.
              </Text>
            </View>
          )}

          {inProgress.filter((item) => item.expedition_id !== active?.expedition_id).length >
            0 && (
            <InProgressList
              activeId={active?.expedition_id ?? null}
              items={inProgress}
              onFocus={(id) => focus.mutate(id)}
              focusing={focus.isPending ? focus.variables ?? null : null}
            />
          )}

          <Text style={styles.sectionLabel}>Where are you?</Text>
          <View style={styles.chipRow}>
            {ENVIRONMENT_CHIPS.map((chip) => (
              <Pressable
                key={chip.label}
                style={[
                  styles.chip,
                  chip.value === env ? styles.chipSelected : styles.chipGhost,
                ]}
                onPress={() => setEnv(chip.value)}
              >
                <Text
                  style={[
                    styles.chipText,
                    chip.value === env && styles.chipTextSelected,
                  ]}
                >
                  {chip.label}
                </Text>
              </Pressable>
            ))}
          </View>
          <Text style={styles.sectionLabel}>Available quests</Text>
        </View>
      }
      ListFooterComponent={
        completed.length === 0 ? null : <TrophyList items={completed} />
      }
      ListEmptyComponent={
        <View style={styles.emptyPanel}>
          <Text style={styles.emptyTitle}>
            {env ? "Nothing for this spot" : "No quests available"}
          </Text>
          <Text style={styles.emptyText}>
            {env
              ? "Tap All to see every unlocked expedition."
              : "You may already be working through every unlocked quest."}
          </Text>
        </View>
      }
      refreshControl={
        <RefreshControl
          refreshing={available.isRefetching || mine.isRefetching}
          onRefresh={() => {
            void available.refetch();
            void mine.refetch();
          }}
        />
      }
      renderItem={({ item }) => (
        <QuestCard
          item={item}
          onStart={() => start.mutate(item.id)}
          starting={start.isPending && start.variables === item.id}
        />
      )}
    />
  );
}

function ActiveMission({ item }: { item: ProgressItem }) {
  const objective = nextObjective(item);
  return (
    <View style={styles.activePanel}>
      <Pressable onPress={() => router.push(`/expedition/${item.expedition_id}`)}>
        <View style={styles.rowTransparent}>
          <FontAwesome name="flag" size={18} color="#0f172a" />
          <Text style={styles.activeKicker}>Active quest</Text>
        </View>
        <Text style={styles.activeTitle}>{item.title}</Text>
        <Text style={styles.activeObjective}>
          {objective?.description ?? "All steps complete"}
        </Text>
      </Pressable>
      <View style={styles.activeActions}>
        <Text style={styles.activeProgress}>{progressLabel(item)}</Text>
        <Pressable
          style={[styles.button, styles.buttonDark]}
          onPress={() => router.push("/observe")}
        >
          <Text style={styles.buttonText}>Open camera</Text>
        </Pressable>
      </View>
    </View>
  );
}

function StarterMission({
  item,
  onStart,
  starting,
}: {
  item: ExpeditionSummary;
  onStart: () => void;
  starting: boolean;
}) {
  return (
    <View style={styles.starterPanel}>
      <Text style={styles.starterKicker}>First mission</Text>
      <Text style={styles.starterTitle}>{item.title}</Text>
      <Text style={styles.starterText}>{item.intro}</Text>
      <Pressable
        style={[styles.button, styles.buttonDark, starting && styles.buttonDisabled]}
        disabled={starting}
        onPress={onStart}
      >
        <Text style={styles.buttonText}>
          {starting ? "Starting..." : "Start quest"}
        </Text>
      </Pressable>
    </View>
  );
}

function InProgressList({
  items,
  activeId,
  onFocus,
  focusing,
}: {
  items: ProgressItem[];
  activeId: string | null;
  onFocus: (id: string) => void;
  focusing: string | null;
}) {
  const otherItems = items.filter((item) => item.expedition_id !== activeId);
  return (
    <View style={styles.section}>
      <Text style={styles.sectionLabel}>Other quests in progress</Text>
      {otherItems.map((p) => (
        <View key={p.expedition_id} style={styles.progressRow}>
          <Pressable
            style={styles.progressBody}
            onPress={() => router.push(`/expedition/${p.expedition_id}`)}
          >
            <Text style={styles.progressTitle}>{p.title}</Text>
            <Text style={styles.progressMeta}>{progressLabel(p)}</Text>
          </Pressable>
          <Pressable
            style={styles.focusButton}
            disabled={focusing === p.expedition_id}
            onPress={() => onFocus(p.expedition_id)}
          >
            <Text style={styles.focusText}>
              {focusing === p.expedition_id ? "..." : "Focus"}
            </Text>
          </Pressable>
        </View>
      ))}
    </View>
  );
}

function TrophyList({ items }: { items: ProgressItem[] }) {
  return (
    <View style={styles.section}>
      <Text style={styles.sectionLabel}>Trophy shelf</Text>
      {items.map((p) => (
        <Pressable
          key={p.expedition_id}
          style={styles.trophyRow}
          onPress={() => router.push(`/expedition/${p.expedition_id}`)}
        >
          <FontAwesome name="trophy" size={15} color="#f6c453" />
          <View style={styles.progressBody}>
            <Text style={styles.progressTitle}>{p.title}</Text>
            <Text style={styles.progressMeta}>
              {p.completed_at
                ? `Completed ${new Date(p.completed_at).toLocaleDateString()}`
                : "Completed"}
            </Text>
          </View>
        </Pressable>
      ))}
    </View>
  );
}

function QuestCard({
  item,
  onStart,
  starting,
}: {
  item: ExpeditionSummary;
  onStart: () => void;
  starting: boolean;
}) {
  const icon = iconForEnvironment(item.environments[0]);
  return (
    <View style={styles.questCard}>
      <View style={styles.questIcon}>
        <FontAwesome name={icon} size={18} color="#fff" />
      </View>
      <View style={styles.questBody}>
        <Text style={styles.cardTitle}>{item.title}</Text>
        {item.subtitle && <Text style={styles.cardSubtitle}>{item.subtitle}</Text>}
        <Text style={styles.cardMeta}>
          {item.duration_minutes} min - {item.environments.join(", ")}
        </Text>
        <RelevanceBadge relevance={item.relevance} />
        <Text style={styles.cardIntro}>{item.intro}</Text>
        <Pressable
          style={[styles.button, styles.buttonPrimary, starting && styles.buttonDisabled]}
          disabled={starting}
          onPress={onStart}
        >
          <Text style={styles.buttonText}>
            {starting ? "Starting..." : "Start quest"}
          </Text>
        </Pressable>
      </View>
    </View>
  );
}

function RelevanceBadge({ relevance }: { relevance?: ExpeditionRelevance }) {
  if (
    !relevance ||
    (relevance.level !== "great_here" && relevance.level !== "tricky_here")
  ) {
    return null;
  }
  const great = relevance.level === "great_here";
  return (
    <>
      <Text
        style={[
          styles.relevanceBadge,
          great ? styles.relevanceGreat : styles.relevanceTricky,
        ]}
      >
        {great ? "Great fit near you" : "A challenge here"}
      </Text>
      {relevance.reason !== null && (
        <Text style={styles.relevanceReason}>{relevance.reason}</Text>
      )}
    </>
  );
}

function iconForEnvironment(
  env: string | undefined,
): ComponentProps<typeof FontAwesome>["name"] {
  switch (env) {
    case "yard":
      return "home";
    case "park":
      return "leaf";
    case "street":
      return "road";
    case "school":
      return "graduation-cap";
    default:
      return "compass";
  }
}

const styles = StyleSheet.create({
  list: { padding: 16, paddingBottom: 28 },
  center: {
    flex: 1,
    alignItems: "center",
    justifyContent: "center",
    padding: 24,
  },
  section: { marginBottom: 14 },
  kicker: {
    color: "#5fbf8f",
    fontSize: 12,
    fontWeight: "800",
    textTransform: "uppercase",
    marginBottom: 4,
  },
  title: { fontSize: 25, fontWeight: "800" },
  subtitle: { fontSize: 14, lineHeight: 20, opacity: 0.75, marginTop: 6, marginBottom: 16 },
  activePanel: {
    backgroundColor: "#8bdcb6",
    borderRadius: 8,
    padding: 16,
    marginBottom: 16,
  },
  rowTransparent: {
    flexDirection: "row",
    alignItems: "center",
    gap: 8,
    backgroundColor: "transparent",
  },
  activeKicker: {
    color: "#0f172a",
    fontSize: 12,
    fontWeight: "800",
    textTransform: "uppercase",
  },
  activeTitle: { color: "#0f172a", fontSize: 21, fontWeight: "800", marginTop: 8 },
  activeObjective: { color: "#0f172a", fontSize: 15, lineHeight: 21, marginTop: 6 },
  activeActions: {
    backgroundColor: "transparent",
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    gap: 12,
    marginTop: 14,
  },
  activeProgress: { color: "#0f172a", fontSize: 13, fontWeight: "700" },
  starterPanel: {
    backgroundColor: "#f6c453",
    borderRadius: 8,
    padding: 16,
    marginBottom: 16,
  },
  starterKicker: {
    color: "#241a05",
    fontSize: 12,
    fontWeight: "800",
    textTransform: "uppercase",
  },
  starterTitle: { color: "#241a05", fontSize: 21, fontWeight: "800", marginTop: 6 },
  starterText: { color: "#241a05", fontSize: 14, lineHeight: 20, marginTop: 6, marginBottom: 12 },
  sectionLabel: {
    fontSize: 13,
    fontWeight: "700",
    opacity: 0.75,
    marginTop: 8,
    marginBottom: 8,
  },
  progressRow: {
    flexDirection: "row",
    alignItems: "center",
    paddingVertical: 12,
    paddingHorizontal: 14,
    borderRadius: 8,
    backgroundColor: "#1a1f2b",
    marginBottom: 8,
  },
  trophyRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: 10,
    paddingVertical: 12,
    paddingHorizontal: 14,
    borderRadius: 8,
    backgroundColor: "#1a1f2b",
    marginBottom: 8,
  },
  progressBody: { flex: 1, backgroundColor: "transparent" },
  progressTitle: { color: "#fff", fontSize: 15, fontWeight: "700" },
  progressMeta: { color: "#cbd5e1", fontSize: 12, marginTop: 2 },
  focusButton: {
    paddingHorizontal: 12,
    paddingVertical: 7,
    borderRadius: 999,
    backgroundColor: "#2f6feb",
  },
  focusText: { color: "#fff", fontSize: 12, fontWeight: "700" },
  chipRow: { flexDirection: "row", flexWrap: "wrap", gap: 8, marginBottom: 8 },
  chip: {
    paddingHorizontal: 12,
    paddingVertical: 6,
    borderRadius: 16,
    alignItems: "center",
  },
  chipSelected: { backgroundColor: "#2f6feb" },
  chipGhost: { borderColor: "#888", borderWidth: StyleSheet.hairlineWidth },
  chipText: { fontSize: 13 },
  chipTextSelected: { color: "#fff" },
  questCard: {
    flexDirection: "row",
    gap: 12,
    paddingVertical: 14,
    paddingHorizontal: 14,
    borderRadius: 8,
    backgroundColor: "#161a22",
    marginBottom: 12,
    borderColor: "rgba(255, 255, 255, 0.08)",
    borderWidth: StyleSheet.hairlineWidth,
  },
  questIcon: {
    width: 38,
    height: 38,
    borderRadius: 19,
    backgroundColor: "#2f6feb",
    alignItems: "center",
    justifyContent: "center",
  },
  questBody: { flex: 1, backgroundColor: "transparent" },
  cardTitle: { color: "#fff", fontSize: 17, fontWeight: "800" },
  cardSubtitle: { color: "#dbeafe", fontSize: 13, marginTop: 2 },
  cardMeta: { color: "#cbd5e1", fontSize: 12, marginTop: 4 },
  relevanceBadge: { fontSize: 12, fontWeight: "700", marginTop: 6 },
  relevanceGreat: { color: "#4ade80" },
  relevanceTricky: { color: "#fbbf24" },
  relevanceReason: { color: "#cbd5e1", fontSize: 12, marginTop: 2 },
  cardIntro: { color: "#e5e7eb", fontSize: 13, marginTop: 9, lineHeight: 18 },
  emptyPanel: {
    alignItems: "center",
    padding: 18,
    borderRadius: 8,
    borderColor: "rgba(95, 191, 143, 0.4)",
    borderWidth: StyleSheet.hairlineWidth,
    marginBottom: 14,
  },
  emptyTitle: { fontSize: 18, fontWeight: "800", marginTop: 8, marginBottom: 6 },
  emptyText: { fontSize: 14, opacity: 0.75, textAlign: "center", lineHeight: 20 },
  button: {
    paddingHorizontal: 14,
    paddingVertical: 9,
    borderRadius: 7,
    alignItems: "center",
  },
  buttonPrimary: { backgroundColor: "#2f6feb", marginTop: 12 },
  buttonDark: { backgroundColor: "#0f172a" },
  buttonGhost: { borderColor: "#888", borderWidth: StyleSheet.hairlineWidth, marginTop: 12 },
  buttonDisabled: { opacity: 0.45 },
  buttonText: { fontSize: 14, color: "#fff", fontWeight: "700" },
});
