/**
 * Sanctuary tab MVP.
 *
 * Stylized diorama built from React Native primitives -- no art assets,
 * no new dependencies. All copy comes from authored content via
 * GET /v1/sanctuary/me (PR #100). The client never fabricates a
 * Sanctuary unlock; this surface is read-only.
 *
 * Safety posture:
 * - No precise location is rendered anywhere (the DTO does not expose
 *   lat/lng/geohash/place_name -- enforced server-side).
 * - No social buttons (share / friend / post / DM / like / follow).
 * - No streak / FOMO copy; the screen only reflects authored content.
 * - No analytics SDK; no LLM imports.
 */

import React, { useCallback, useMemo, useState } from "react";
import {
  ActivityIndicator,
  Modal,
  Pressable,
  RefreshControl,
  ScrollView,
  StyleSheet,
  Text,
  View,
} from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";

import {
  type SanctuaryElementDto,
  type SanctuaryEventDto,
  type SanctuaryJournalEntryDto,
  type SanctuaryMysteryCueDto,
  type SanctuaryZoneDto,
  type SanctuaryZoneId,
  SANCTUARY_ZONE_ORDER,
} from "@/src/api/sanctuary";
import { useSanctuary } from "@/src/sanctuary/useSanctuary";

// ---------------------------------------------------------------------------
// Per-zone visual tokens (placeholder until final illustration lands).
// Each tint nudges the band toward the habitat without requiring assets.
// ---------------------------------------------------------------------------

type ZoneTokens = {
  background: string;
  accent: string;
  symbol: string;
};

const ZONE_TOKENS: Record<SanctuaryZoneId, ZoneTokens> = {
  meadow: { background: "#D7EBC0", accent: "#5C8A2A", symbol: "🌾" },
  woodland: { background: "#CFE0C7", accent: "#3F6B40", symbol: "🌲" },
  pond: { background: "#C7E5E8", accent: "#3F7B86", symbol: "💧" },
  sky: { background: "#D8E8F2", accent: "#4A6B8A", symbol: "☁︎" },
  soil: { background: "#E1D2BB", accent: "#6E5235", symbol: "·" },
  urban: { background: "#D9D6D2", accent: "#4F4F4F", symbol: "▮" },
  elsewhere: { background: "#E4E1E6", accent: "#6B6573", symbol: "✦" },
};

// ---------------------------------------------------------------------------
// Screen
// ---------------------------------------------------------------------------

export default function SanctuaryScreen() {
  const { data, isLoading, isError, error, refetch, isRefetching } = useSanctuary();
  const [inspectedElement, setInspectedElement] = useState<SanctuaryElementDto | null>(null);

  const onRefresh = useCallback(() => {
    void refetch();
  }, [refetch]);

  if (isLoading) {
    return (
      <SafeAreaView style={styles.centered} edges={["top"]}>
        <ActivityIndicator />
        <Text style={styles.centeredText}>Waking up…</Text>
      </SafeAreaView>
    );
  }

  if (isError || !data) {
    return (
      <SafeAreaView style={styles.centered} edges={["top"]}>
        <Text style={styles.centeredTitle}>Couldn't reach your Sanctuary</Text>
        <Text style={styles.centeredText}>
          {error?.message ?? "Try again in a moment."}
        </Text>
        <Pressable
          accessibilityRole="button"
          style={styles.retryButton}
          onPress={onRefresh}
        >
          <Text style={styles.retryButtonText}>Retry</Text>
        </Pressable>
      </SafeAreaView>
    );
  }

  const anyUnlocked = data.zones.some((z) => z.unlocked);
  const hasAnyElements = data.elements.length > 0;
  const isEmptyState = !anyUnlocked && !hasAnyElements;

  return (
    <SafeAreaView style={styles.root} edges={["top"]}>
      <ScrollView
        contentContainerStyle={styles.scrollContent}
        refreshControl={
          <RefreshControl refreshing={isRefetching} onRefresh={onRefresh} />
        }
      >
        <Header />
        <GuideBar text={data.guide_message.text} />
        {isEmptyState ? (
          <EmptyStateHint />
        ) : null}
        <Diorama
          zones={data.zones}
          elements={data.elements}
          onInspect={setInspectedElement}
        />
        {data.mystery_cues.length > 0 ? (
          <MysteryCuesPanel cues={data.mystery_cues} />
        ) : null}
        {data.recent_events.length > 0 || data.journal.length > 0 ? (
          <JournalPanel
            recentEvents={data.recent_events}
            journal={data.journal}
          />
        ) : null}
        <View style={styles.footerSpacer} />
      </ScrollView>
      <ElementInspectModal
        element={inspectedElement}
        onClose={() => setInspectedElement(null)}
      />
    </SafeAreaView>
  );
}

// ---------------------------------------------------------------------------
// Sub-components
// ---------------------------------------------------------------------------

function Header() {
  return (
    <View style={styles.header}>
      <Text style={styles.headerTitle}>Sanctuary</Text>
      <Text style={styles.headerSubtitle}>
        A quiet place that grows when you go outside.
      </Text>
    </View>
  );
}

function GuideBar({ text }: { text: string }) {
  return (
    <View style={styles.guideBar} accessibilityRole="text">
      <Text style={styles.guideBarSpeaker}>Dragonfly</Text>
      <Text style={styles.guideBarText}>{text}</Text>
    </View>
  );
}

function EmptyStateHint() {
  return (
    <View style={styles.emptyHint}>
      <Text style={styles.emptyHintText}>
        Log a real observation outside to wake your Sanctuary.
      </Text>
    </View>
  );
}

function Diorama({
  zones,
  elements,
  onInspect,
}: {
  zones: SanctuaryZoneDto[];
  elements: SanctuaryElementDto[];
  onInspect: (element: SanctuaryElementDto) => void;
}) {
  // Render zones in authored order, regardless of how the server returned
  // them. The backend already returns authored order, but defending in
  // depth is cheap.
  const orderedZones = useMemo(() => {
    const byId = new Map(zones.map((z) => [z.zone_id, z] as const));
    return SANCTUARY_ZONE_ORDER.map((id) => byId.get(id)).filter(
      (z): z is SanctuaryZoneDto => z !== undefined,
    );
  }, [zones]);

  const elementsByZone = useMemo(() => {
    const map = new Map<SanctuaryZoneId, SanctuaryElementDto[]>();
    for (const element of elements) {
      const list = map.get(element.zone_id) ?? [];
      list.push(element);
      map.set(element.zone_id, list);
    }
    return map;
  }, [elements]);

  return (
    <View style={styles.diorama}>
      {orderedZones.map((zone) => (
        <ZoneBand
          key={zone.zone_id}
          zone={zone}
          elements={elementsByZone.get(zone.zone_id) ?? []}
          onInspect={onInspect}
        />
      ))}
    </View>
  );
}

function ZoneBand({
  zone,
  elements,
  onInspect,
}: {
  zone: SanctuaryZoneDto;
  elements: SanctuaryElementDto[];
  onInspect: (element: SanctuaryElementDto) => void;
}) {
  const tokens = ZONE_TOKENS[zone.zone_id];
  const bandStyle = [
    styles.band,
    { backgroundColor: tokens.background },
    zone.unlocked ? null : styles.bandLocked,
  ];
  const nextLabel =
    zone.next_threshold === null
      ? "Maxed"
      : `Next at ${zone.next_threshold}`;

  return (
    <View style={bandStyle} accessibilityLabel={`${zone.title} zone`}>
      <View style={styles.bandHeaderRow}>
        <Text style={[styles.bandSymbol, { color: tokens.accent }]}>
          {tokens.symbol}
        </Text>
        <View style={styles.bandHeaderText}>
          <Text style={[styles.bandTitle, { color: tokens.accent }]}>
            {zone.title}
          </Text>
          <Text style={styles.bandMood} numberOfLines={2}>
            {zone.mood}
          </Text>
        </View>
        <View style={styles.bandMeta}>
          {zone.unlocked ? (
            <>
              <Text style={styles.bandMetaCount}>{zone.observation_count}</Text>
              <Text style={styles.bandMetaLabel}>{nextLabel}</Text>
            </>
          ) : (
            <Text style={styles.bandLockedText}>Locked</Text>
          )}
        </View>
      </View>
      {zone.unlocked && zone.depth_tier > 0 ? (
        <View style={styles.tierRow}>
          {[1, 3, 5, 10, 20, 50].map((tier) => (
            <View
              key={tier}
              style={[
                styles.tierDot,
                {
                  backgroundColor:
                    tier <= zone.depth_tier ? tokens.accent : "transparent",
                  borderColor: tokens.accent,
                },
              ]}
            />
          ))}
        </View>
      ) : null}
      {elements.length > 0 ? (
        <View style={styles.chipRow}>
          {elements.map((element) => (
            <Pressable
              key={element.element_id}
              accessibilityRole="button"
              accessibilityLabel={element.title}
              hitSlop={8}
              style={({ pressed }) => [
                styles.chip,
                { borderColor: tokens.accent },
                pressed ? styles.chipPressed : null,
              ]}
              onPress={() => onInspect(element)}
            >
              <Text style={[styles.chipText, { color: tokens.accent }]}>
                {element.title}
              </Text>
            </Pressable>
          ))}
        </View>
      ) : null}
    </View>
  );
}

function MysteryCuesPanel({ cues }: { cues: SanctuaryMysteryCueDto[] }) {
  return (
    <View style={styles.panel}>
      <Text style={styles.panelTitle}>Quiet corners</Text>
      {cues.map((cue) => (
        <View key={cue.zone_id} style={styles.cue}>
          <Text style={styles.cueTitle}>{cue.title}</Text>
          <Text style={styles.cueDetail}>{cue.detail}</Text>
        </View>
      ))}
    </View>
  );
}

function JournalPanel({
  recentEvents,
  journal,
}: {
  recentEvents: SanctuaryEventDto[];
  journal: SanctuaryJournalEntryDto[];
}) {
  // Prefer the explicit journal (oldest-first, deterministic from the
  // same recent-set). If the server returned no journal entries, fall
  // back to the chronological recent_events list.
  const entries: ReadonlyArray<{
    key: string;
    title: string;
    detail: string | null;
    created_at: string;
  }> =
    journal.length > 0
      ? journal.map((j, i) => ({
          key: `j-${i}-${j.created_at}`,
          title: j.title,
          detail: j.detail,
          created_at: j.created_at,
        }))
      : recentEvents.map((e, i) => ({
          key: `e-${i}-${e.created_at}`,
          title: e.title,
          detail: e.detail,
          created_at: e.created_at,
        }));

  return (
    <View style={styles.panel}>
      <Text style={styles.panelTitle}>Journal</Text>
      {entries.map((entry) => (
        <View key={entry.key} style={styles.journalRow}>
          <Text style={styles.journalRowTitle}>{entry.title}</Text>
          {entry.detail ? (
            <Text style={styles.journalRowDetail}>{entry.detail}</Text>
          ) : null}
          <Text style={styles.journalRowDate}>
            {_formatDate(entry.created_at)}
          </Text>
        </View>
      ))}
    </View>
  );
}

function ElementInspectModal({
  element,
  onClose,
}: {
  element: SanctuaryElementDto | null;
  onClose: () => void;
}) {
  return (
    <Modal
      visible={element !== null}
      animationType="fade"
      transparent
      onRequestClose={onClose}
    >
      <Pressable
        accessibilityRole="button"
        accessibilityLabel="Close inspector"
        style={styles.modalBackdrop}
        onPress={onClose}
      >
        {/* Inner card stops the backdrop tap by being its own Pressable
            that calls a no-op handler -- React Native does not have a
            DOM-style event.stopPropagation, but tapping a child Pressable
            consumes the gesture before the parent sees it. */}
        <Pressable
          accessibilityRole="none"
          style={styles.modalCard}
          onPress={() => {
            /* swallow taps so the backdrop close handler is not invoked */
          }}
        >
          {element ? (
            <>
              <View style={styles.modalBadge}>
                <Text style={styles.modalBadgeText}>{element.element_type}</Text>
              </View>
              <Text style={styles.modalTitle}>{element.title}</Text>
              <Text style={styles.modalDetail}>{element.detail}</Text>
              <Text style={styles.modalIcon}>{element.icon}</Text>
              <Pressable
                accessibilityRole="button"
                style={styles.modalCloseButton}
                onPress={onClose}
              >
                <Text style={styles.modalCloseButtonText}>Close</Text>
              </Pressable>
            </>
          ) : null}
        </Pressable>
      </Pressable>
    </Modal>
  );
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function _formatDate(iso: string): string {
  // Date-only string is enough for an MVP journal row -- avoid locale
  // surprises by using a fixed yyyy-mm-dd format.
  const date = new Date(iso);
  if (Number.isNaN(date.valueOf())) {
    return iso;
  }
  const y = date.getFullYear();
  const m = String(date.getMonth() + 1).padStart(2, "0");
  const d = String(date.getDate()).padStart(2, "0");
  return `${y}-${m}-${d}`;
}

// ---------------------------------------------------------------------------
// Styles
// ---------------------------------------------------------------------------

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: "#F7F6F2" },
  centered: {
    flex: 1,
    alignItems: "center",
    justifyContent: "center",
    padding: 24,
    backgroundColor: "#F7F6F2",
  },
  centeredTitle: { fontSize: 18, fontWeight: "600", marginBottom: 8 },
  centeredText: { fontSize: 14, color: "#666", marginTop: 8 },
  retryButton: {
    marginTop: 16,
    paddingVertical: 8,
    paddingHorizontal: 16,
    borderRadius: 8,
    backgroundColor: "#3F6B40",
  },
  retryButtonText: { color: "#fff", fontSize: 14, fontWeight: "500" },
  scrollContent: { padding: 16, gap: 12 },
  header: { marginBottom: 4 },
  headerTitle: { fontSize: 24, fontWeight: "700", color: "#2A2A2A" },
  headerSubtitle: { fontSize: 13, color: "#666", marginTop: 2 },
  guideBar: {
    backgroundColor: "#FFFDF5",
    borderLeftWidth: 3,
    borderLeftColor: "#7BA45A",
    paddingVertical: 10,
    paddingHorizontal: 12,
    borderRadius: 8,
  },
  guideBarSpeaker: {
    fontSize: 11,
    fontWeight: "600",
    color: "#7BA45A",
    textTransform: "uppercase",
    letterSpacing: 1,
    marginBottom: 2,
  },
  guideBarText: { fontSize: 14, color: "#3A3A3A", lineHeight: 20 },
  emptyHint: {
    backgroundColor: "#F2EEE3",
    padding: 12,
    borderRadius: 8,
  },
  emptyHintText: { fontSize: 13, color: "#555", textAlign: "center" },
  diorama: { gap: 10 },
  band: {
    borderRadius: 10,
    padding: 12,
    overflow: "hidden",
  },
  bandLocked: {
    opacity: 0.45,
  },
  bandHeaderRow: { flexDirection: "row", alignItems: "center", gap: 12 },
  bandSymbol: { fontSize: 24, width: 28, textAlign: "center" },
  bandHeaderText: { flex: 1 },
  bandTitle: { fontSize: 16, fontWeight: "600" },
  bandMood: { fontSize: 12, color: "#4A4A4A", marginTop: 2 },
  bandMeta: { alignItems: "flex-end", minWidth: 72 },
  bandMetaCount: { fontSize: 18, fontWeight: "700", color: "#2A2A2A" },
  bandMetaLabel: { fontSize: 11, color: "#555" },
  bandLockedText: {
    fontSize: 11,
    textTransform: "uppercase",
    letterSpacing: 1,
    color: "#666",
  },
  tierRow: { flexDirection: "row", gap: 6, marginTop: 10 },
  tierDot: {
    width: 10,
    height: 10,
    borderRadius: 5,
    borderWidth: 1.5,
  },
  chipRow: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: 8,
    marginTop: 10,
  },
  chip: {
    paddingVertical: 6,
    paddingHorizontal: 10,
    borderRadius: 999,
    borderWidth: 1,
    backgroundColor: "#FFFFFFAA",
  },
  chipPressed: { opacity: 0.6 },
  chipText: { fontSize: 12, fontWeight: "500" },
  panel: {
    backgroundColor: "#FFFFFF",
    padding: 14,
    borderRadius: 10,
    gap: 10,
  },
  panelTitle: {
    fontSize: 14,
    fontWeight: "600",
    color: "#2A2A2A",
    textTransform: "uppercase",
    letterSpacing: 1,
  },
  cue: { borderTopWidth: StyleSheet.hairlineWidth, borderTopColor: "#E5E0D6", paddingTop: 8 },
  cueTitle: { fontSize: 14, color: "#2A2A2A", fontWeight: "500" },
  cueDetail: { fontSize: 13, color: "#666", marginTop: 2, lineHeight: 18 },
  journalRow: {
    borderTopWidth: StyleSheet.hairlineWidth,
    borderTopColor: "#E5E0D6",
    paddingTop: 8,
  },
  journalRowTitle: { fontSize: 14, color: "#2A2A2A", fontWeight: "500" },
  journalRowDetail: { fontSize: 13, color: "#666", marginTop: 2, lineHeight: 18 },
  journalRowDate: { fontSize: 11, color: "#888", marginTop: 4 },
  footerSpacer: { height: 32 },
  modalBackdrop: {
    flex: 1,
    backgroundColor: "rgba(0,0,0,0.4)",
    justifyContent: "center",
    alignItems: "center",
    padding: 24,
  },
  modalCard: {
    backgroundColor: "#FFFFFF",
    borderRadius: 12,
    padding: 20,
    width: "100%",
    maxWidth: 360,
    gap: 10,
  },
  modalBadge: {
    alignSelf: "flex-start",
    backgroundColor: "#EEF2E6",
    paddingHorizontal: 8,
    paddingVertical: 3,
    borderRadius: 999,
  },
  modalBadgeText: {
    fontSize: 11,
    color: "#5C8A2A",
    textTransform: "uppercase",
    letterSpacing: 1,
  },
  modalTitle: { fontSize: 18, fontWeight: "600", color: "#2A2A2A" },
  modalDetail: { fontSize: 14, color: "#3A3A3A", lineHeight: 20 },
  modalIcon: { fontSize: 12, color: "#888", fontFamily: "Courier" },
  modalCloseButton: {
    alignSelf: "flex-end",
    paddingVertical: 8,
    paddingHorizontal: 14,
    borderRadius: 8,
    backgroundColor: "#3F6B40",
  },
  modalCloseButtonText: { color: "#FFFFFF", fontSize: 14, fontWeight: "500" },
});
