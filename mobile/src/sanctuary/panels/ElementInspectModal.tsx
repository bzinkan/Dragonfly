/**
 * Element inspector modal, shared by the classic (2D) Sanctuary screen and
 * the D7 diorama screen. Extracted verbatim from the tab-route screen so
 * both render paths open the exact same kid-facing card. Read-only: title,
 * detail, and icon key come straight from authored content -- no social
 * actions, no links out.
 */

import React from "react";
import { Modal, Pressable, StyleSheet, Text, View } from "react-native";

import type { SanctuaryElementDto } from "@/src/api/sanctuary";

export function ElementInspectModal({
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

const styles = StyleSheet.create({
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
