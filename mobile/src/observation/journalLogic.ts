/**
 * Pure display rules for the Field Journal. Kept out of the component so
 * jest can pin the status -> presentation mapping without a renderer.
 *
 * `child_presentation_status` is derived server-side from matching
 * Observation/Photo lifecycle rows plus revocation state. Mobile treats it
 * as the only image-eligibility authority; unknown values remain metadata-only.
 */

import type { DexListItem } from "@/src/api/dex";
import type {
  ChildPresentationStatus,
  ObservationListItem,
} from "@/src/api/observations";
import type { QueuedObservation } from "@/src/observation/queueTypes";

export const DEFAULT_JOURNAL_MODE = "photos" as const;

export type JournalMode = "photos" | "species";
export type PhotoDisplayMode = "image" | "metadata" | "removed";

/** Give status copy room when the device is narrow or system text is enlarged. */
export function journalColumnCount(width: number, fontScale: number): 1 | 2 {
  return width < 360 || fontScale >= 1.3 ? 1 : 2;
}

export type ChildPhotoPresentation = {
  status: ChildPresentationStatus;
  mode: Exclude<PhotoDisplayMode, "removed">;
  message: string | null;
};

const PRESENTATIONS: Record<ChildPresentationStatus, ChildPhotoPresentation> = {
  clean: { status: "clean", mode: "image", message: null },
  pending: {
    status: "pending",
    mode: "metadata",
    message: "This photo is being checked.",
  },
  processing: {
    status: "processing",
    mode: "metadata",
    message: "This photo is being checked.",
  },
  pilot_private: {
    status: "pilot_private",
    mode: "metadata",
    message: "This photo is private during the pilot.",
  },
  adult_review: {
    status: "adult_review",
    mode: "metadata",
    message: "An adult is reviewing this photo.",
  },
  failed: {
    status: "failed",
    mode: "metadata",
    message: "This photo is private while we sort out a check.",
  },
};

/**
 * Mobile consumes the server-derived status. Unknown values fail closed to
 * the most restrictive non-image presentation and never mint a photo URL.
 */
export function childPhotoPresentation(status: string): ChildPhotoPresentation {
  if (status === "quarantine") return PRESENTATIONS.adult_review;
  if (status === "rejected" || status === "deleted") {
    return {
      status: "failed",
      mode: "metadata",
      message: "This Field Journal entry isn’t available.",
    };
  }
  return PRESENTATIONS[status as ChildPresentationStatus] ?? PRESENTATIONS.failed;
}

export function childRecordIsVisible(status: string): boolean {
  return status !== "rejected" && status !== "deleted";
}

export function visibleJournalItems(items: ObservationListItem[]): ObservationListItem[] {
  return items.filter((item) =>
    childRecordIsVisible(String(item.child_presentation_status)),
  );
}

export function photoDisplayMode(photoStatus: string): PhotoDisplayMode {
  if (photoStatus === "deleted" || photoStatus === "rejected") return "removed";
  return childPhotoPresentation(photoStatus).mode;
}

/** True while moderation has not produced a clean result. Callers use this
 * only for explanatory copy; these statuses never enable a signed photo. */
export function isAwaitingModeration(photoStatus: string): boolean {
  return ["pending", "processing", "pilot_private", "failed"].includes(
    photoStatus,
  );
}

export function representativePhotoId(item: DexListItem): string | null {
  if (item.representative_photo_id) return item.representative_photo_id;
  return item.first_photo_status === "clean" ? (item.first_photo_id ?? null) : null;
}

/** Queue records remain metadata-only and disappear after server reconciliation. */
export function waitingQueueItems(
  queue: QueuedObservation[],
  serverItems: ObservationListItem[],
): QueuedObservation[] {
  const serverIds = new Set(serverItems.map((item) => item.id));
  const serverSubmissionKeys = new Set(
    serverItems
      .map((item) => item.submission_ulid)
      .filter((key): key is string => typeof key === "string" && key.length > 0),
  );
  return queue
    .filter((item) => item.stage !== "complete" && item.stage !== "abandoned")
    .filter((item) => !item.observationId || !serverIds.has(item.observationId))
    .filter((item) => !serverSubmissionKeys.has(item.submissionKey))
    .sort((left, right) => {
      const observed = Date.parse(right.observedAt) - Date.parse(left.observedAt);
      return observed || right.submissionKey.localeCompare(left.submissionKey);
    });
}

export function queueStatusMessage(item: QueuedObservation): string {
  return item.stage === "needs_attention"
    ? "An adult needs to help finish syncing this entry."
    : "Waiting to sync. Your saved work is safe.";
}

/** Card caption. Kids often skip the species pick; "Mystery find" reads
 * better than a null. */
export function journalCaption(speciesName: string | null): string {
  const trimmed = speciesName?.trim();
  return trimmed ? trimmed : "Mystery find";
}

export function speciesDisplayName(item: DexListItem): string {
  return (
    item.common_name?.trim() ||
    item.species_name?.trim() ||
    item.scientific_name?.trim() ||
    `Taxon ${item.taxon_id}`
  );
}

export function speciesSubtitle(item: DexListItem): string {
  const parts = [
    item.scientific_name?.trim(),
    item.iconic_taxon?.trim(),
  ].filter(Boolean);
  return parts.length > 0 ? parts.join(" - ") : "Verified species";
}

export function findCountLabel(count: number): string {
  return `${count} ${count === 1 ? "find" : "finds"}`;
}

/**
 * True while a signed URL is safe to hand to <Image>. 10s margin: a URL
 * used right at the SAS edge 403s mid-download. Callers fall back to the
 * loading placeholder when false -- the background refetch re-mints.
 */
export function isUrlUsable(expiresAt: string): boolean {
  return Date.parse(expiresAt) - 10_000 > Date.now();
}
