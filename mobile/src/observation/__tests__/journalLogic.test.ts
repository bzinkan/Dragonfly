import type { DexListItem } from "@/src/api/dex";
import type { ObservationListItem } from "@/src/api/observations";
import type { QueuedObservation } from "@/src/observation/queueTypes";
import {
  PHOTO_URL_GC_MS,
  PHOTO_URL_STALE_MS,
} from "@/src/observation/usePhotoUrl";
import {
  childPhotoPresentation,
  childRecordIsVisible,
  DEFAULT_JOURNAL_MODE,
  findCountLabel,
  isUrlUsable,
  journalColumnCount,
  journalCaption,
  photoDisplayMode,
  queueStatusMessage,
  representativePhotoId,
  speciesDisplayName,
  speciesSubtitle,
  waitingQueueItems,
  visibleJournalItems,
} from "@/src/observation/journalLogic";

function dexItem(overrides: Partial<DexListItem> = {}): DexListItem {
  return {
    id: "dex-1",
    taxon_id: 12345,
    species_name: "Cached display",
    common_name: "Yellow Cosmos",
    scientific_name: "Cosmos sulphureus",
    iconic_taxon: "Plantae",
    first_observation_id: "obs-1",
    first_photo_id: "photo-1",
    first_photo_status: "clean",
    first_seen_at: "2026-07-06T12:00:00Z",
    observation_count: 1,
    latest_seen_at: "2026-07-07T12:00:00Z",
    ...overrides,
  };
}

function queued(
  submissionKey: string,
  overrides: Partial<QueuedObservation> = {},
): QueuedObservation {
  return {
    submissionKey,
    ownerUserId: "kid-1",
    localUri: "file:///private.jpg",
    width: 100,
    height: 100,
    byteCount: 10,
    sha256: "a".repeat(64),
    source: "camera",
    observedAt: "2026-07-07T12:00:00Z",
    geohash4: null,
    locationSource: "none",
    identification: { source: "unknown", taxonId: null, speciesName: null },
    placeName: null,
    ecologyTags: {},
    payloadFrozen: true,
    photoId: null,
    uploadUrl: null,
    uploadHeaders: null,
    observationId: null,
    observation: null,
    stage: "ready",
    attempts: 0,
    nextAttemptAt: null,
    lastErrorCode: null,
    lastRequestId: null,
    failureStage: null,
    lastFailureRetryable: null,
    createdAt: "2026-07-07T12:00:00Z",
    updatedAt: "2026-07-07T12:00:00Z",
    ...overrides,
  };
}

function observation(overrides: Partial<ObservationListItem> = {}): ObservationListItem {
  return {
    id: "obs-1",
    photo_id: "photo-1",
    submission_ulid: "server-key",
    geohash4: null,
    observed_at: "2026-07-07T12:00:00Z",
    location_source: "none",
    taxon_id: null,
    species_name: null,
    identification_source: "unknown",
    place_name: null,
    child_presentation_status: "pilot_private",
    dispatch_status: "complete",
    ...overrides,
  };
}

describe("Field Journal display rules", () => {
  it("gives enlarged text and narrow screens a single-column layout", () => {
    expect(journalColumnCount(412, 1)).toBe(2);
    expect(journalColumnCount(359, 1)).toBe(1);
    expect(journalColumnCount(412, 1.3)).toBe(1);
  });

  test("defaults to photos first", () => {
    expect(DEFAULT_JOURNAL_MODE).toBe("photos");
  });

  test("maps every status to exact truthful child copy", () => {
    expect(childPhotoPresentation("pilot_private").message).toBe(
      "This photo is private during the pilot.",
    );
    expect(childPhotoPresentation("pending").message).toBe(
      "This photo is being checked.",
    );
    expect(childPhotoPresentation("processing").message).toBe(
      "This photo is being checked.",
    );
    expect(childPhotoPresentation("adult_review").message).toBe(
      "An adult is reviewing this photo.",
    );
    expect(childPhotoPresentation("failed").message).toBe(
      "This photo is private while we sort out a check.",
    );
    expect(childPhotoPresentation("future-status")).toEqual(
      childPhotoPresentation("failed"),
    );
    expect(photoDisplayMode("pending")).toBe("metadata");
    expect(photoDisplayMode("clean")).toBe("image");
    expect(photoDisplayMode("pilot_private")).toBe("metadata");
    expect(photoDisplayMode("quarantine")).toBe("metadata");
    expect(photoDisplayMode("rejected")).toBe("removed");
    expect(photoDisplayMode("deleted")).toBe("removed");
    expect(photoDisplayMode("future-status")).toBe("metadata");
    expect(childRecordIsVisible("rejected")).toBe(false);
    expect(childRecordIsVisible("deleted")).toBe(false);
    expect(childRecordIsVisible("future-status")).toBe(true);
    expect(
      visibleJournalItems([
        observation(),
        observation({ id: "rejected", child_presentation_status: "rejected" as never }),
      ]).map((item) => item.id),
    ).toEqual(["obs-1"]);
  });

  test("uses mystery caption for unnamed observations", () => {
    expect(journalCaption(null)).toBe("Mystery find");
    expect(journalCaption("  ")).toBe("Mystery find");
    expect(journalCaption("Yellow Cosmos")).toBe("Yellow Cosmos");
  });

  test("prefers verified species display names in order", () => {
    expect(speciesDisplayName(dexItem())).toBe("Yellow Cosmos");
    expect(speciesDisplayName(dexItem({ common_name: null }))).toBe("Cached display");
    expect(
      speciesDisplayName(
        dexItem({
          common_name: null,
          species_name: null,
        }),
      ),
    ).toBe("Cosmos sulphureus");
    expect(
      speciesDisplayName(
        dexItem({
          common_name: null,
          species_name: null,
          scientific_name: null,
        }),
      ),
    ).toBe("Taxon 12345");
  });

  test("formats species subtitles and counts", () => {
    expect(speciesSubtitle(dexItem())).toBe("Cosmos sulphureus - Plantae");
    expect(
      speciesSubtitle(
        dexItem({
          scientific_name: null,
          iconic_taxon: null,
        }),
      ),
    ).toBe("Verified species");
    expect(findCountLabel(1)).toBe("1 find");
    expect(findCountLabel(2)).toBe("2 finds");
  });

  test("uses only the maintained representative clean photo", () => {
    expect(representativePhotoId(dexItem({ representative_photo_id: "photo-2" }))).toBe("photo-2");
    expect(representativePhotoId(dexItem({ first_photo_status: "pending" }))).toBeNull();
  });

  test("dedupes and chronologically sorts owner-scoped waiting work", () => {
    const items = waitingQueueItems(
      [
        queued("keep-old"),
        queued("keep-new", { observedAt: "2026-07-08T12:00:00Z" }),
        queued("by-observation", { observationId: "obs-1", stage: "uploaded" }),
        queued("server-key", { stage: "presigned" }),
        queued("done", { stage: "complete" }),
      ],
      [observation()],
    );
    expect(items.map((item) => item.submissionKey)).toEqual(["keep-new", "keep-old"]);
    expect(queueStatusMessage(items[0])).toContain("saved work is safe");
    expect(queueStatusMessage(queued("attention", { stage: "needs_attention" }))).toContain(
      "adult needs to help",
    );
  });

  test("rejects expired or malformed signed URLs", () => {
    jest.spyOn(Date, "now").mockReturnValue(Date.parse("2026-07-07T12:00:00Z"));

    expect(isUrlUsable("2026-07-07T12:00:11Z")).toBe(true);
    expect(isUrlUsable("2026-07-07T12:00:10Z")).toBe(false);
    expect(isUrlUsable("not-a-date")).toBe(false);

    jest.restoreAllMocks();
  });

  test("refreshes before the 60-second server SAS bound", () => {
    expect(PHOTO_URL_STALE_MS).toBe(40_000);
    expect(PHOTO_URL_GC_MS).toBe(60_000);
  });
});
