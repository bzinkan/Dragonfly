import type { RewardType } from "@/src/api/observations";
import { childPhotoPresentation } from "@/src/observation/journalLogic";

export const OBSERVATION_FLOW_STEPS = [
  { key: "photo", label: "Photo" },
  { key: "place", label: "Place" },
  { key: "identify", label: "ID" },
  { key: "upload", label: "Upload" },
  { key: "saved", label: "Saved" },
] as const;

export type ObservationFlowStep = (typeof OBSERVATION_FLOW_STEPS)[number]["key"];

export type FlowStepState = "complete" | "active" | "upcoming";

export function flowStepState(
  current: ObservationFlowStep,
  step: ObservationFlowStep,
): FlowStepState {
  const currentIndex = OBSERVATION_FLOW_STEPS.findIndex((s) => s.key === current);
  const stepIndex = OBSERVATION_FLOW_STEPS.findIndex((s) => s.key === step);
  if (stepIndex < currentIndex) return "complete";
  if (stepIndex === currentIndex) return "active";
  return "upcoming";
}

export function photoStatusLabel(status: string): string {
  return childPhotoPresentation(status).message ?? "Approved";
}

export type PhotoStatusTone = "neutral" | "success" | "warning" | "danger";

export function photoStatusTone(status: string): PhotoStatusTone {
  switch (status) {
    case "clean":
      return "success";
    case "quarantine":
    case "adult_review":
    case "failed":
      return "warning";
    case "deleted":
    case "rejected":
      return "danger";
    default:
      return "neutral";
  }
}

export function rewardLabel(type: RewardType): string {
  switch (type) {
    case "first_find":
      return "Dex";
    case "repeat_find":
      return "Logged";
    case "expedition_step":
      return "Expedition";
    case "expedition_complete":
      return "Complete";
    case "rarity_tier":
    case "unrecorded":
      return "Rarity";
    case "world_unlock":
    case "world_evolution":
      return "Sanctuary";
    case "territory_claimed":
      return "Territory";
    case "season_hit":
      return "Season";
    case "mission_progress":
    case "mission_complete":
      return "Mission";
  }
}
