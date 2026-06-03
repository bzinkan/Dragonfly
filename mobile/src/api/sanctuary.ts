/**
 * Sanctuary read API client.
 *
 * Mirrors the snake_case wire shape of ``GET /v1/sanctuary/me`` from
 * ``docs/sanctuary.md`` section 9. Field names match the backend DTOs in
 * ``backend/app/api/routes/sanctuary.py`` so the JSON deserializes by
 * structural assignment (no key renaming on the client).
 */

import { apiRequest } from "@/src/api/client";

// ---------------------------------------------------------------------------
// Vocabularies
// ---------------------------------------------------------------------------

export type SanctuaryZoneId =
  | "meadow"
  | "woodland"
  | "pond"
  | "sky"
  | "soil"
  | "urban"
  | "elsewhere";

export type SanctuaryElementType =
  | "coarse"
  | "charismatic"
  | "relationship"
  | "surprise"
  | "signature";

export type SanctuaryEventType =
  | "world_unlock"
  | "world_evolution"
  | "relationship"
  | "surprise";

/** Authored zone order. The backend always returns zones in this order. */
export const SANCTUARY_ZONE_ORDER: readonly SanctuaryZoneId[] = [
  "meadow",
  "woodland",
  "pond",
  "sky",
  "soil",
  "urban",
  "elsewhere",
];

// ---------------------------------------------------------------------------
// DTOs (match backend response 1:1)
// ---------------------------------------------------------------------------

export type SanctuaryZoneDto = {
  zone_id: SanctuaryZoneId;
  title: string;
  mood: string;
  description: string;
  observation_count: number;
  depth_tier: number;
  unlocked: boolean;
  next_threshold: number | null;
  accent: string | null;
};

export type SanctuaryElementDto = {
  element_id: string;
  zone_id: SanctuaryZoneId;
  element_type: SanctuaryElementType;
  title: string;
  detail: string;
  icon: string;
  taxon_id: number | null;
  source_observation_id: string | null;
  unlocked_at: string;
  payload: Record<string, unknown>;
};

export type SanctuaryEventDto = {
  event_type: SanctuaryEventType;
  zone_id: SanctuaryZoneId | null;
  element_id: string | null;
  title: string;
  detail: string | null;
  created_at: string;
  payload: Record<string, unknown>;
};

export type SanctuaryGuideMessageDto = {
  speaker: "dragonfly";
  text: string;
};

export type SanctuaryMysteryCueDto = {
  zone_id: SanctuaryZoneId;
  title: string;
  detail: string;
};

export type SanctuaryJournalEntryDto = {
  event_type: SanctuaryEventType;
  zone_id: SanctuaryZoneId | null;
  element_id: string | null;
  title: string;
  detail: string | null;
  created_at: string;
};

export type SanctuarySnapshotDto = {
  zones: SanctuaryZoneDto[];
  elements: SanctuaryElementDto[];
  recent_events: SanctuaryEventDto[];
  guide_message: SanctuaryGuideMessageDto;
  mystery_cues: SanctuaryMysteryCueDto[];
  journal: SanctuaryJournalEntryDto[];
};

// ---------------------------------------------------------------------------
// GET /v1/sanctuary/me
// ---------------------------------------------------------------------------

/**
 * Fetch the signed-in user's Sanctuary snapshot.
 *
 * Read-only, current-user-scoped. The route takes no parameters; a hostile
 * caller cannot pass `?user_id=...` to fetch another user's Sanctuary.
 */
export function getMySanctuary(): Promise<SanctuarySnapshotDto> {
  return apiRequest<SanctuarySnapshotDto>("/v1/sanctuary/me");
}
