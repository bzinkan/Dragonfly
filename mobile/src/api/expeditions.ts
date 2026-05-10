import { apiRequest } from "@/src/api/client";

export type ExpeditionSummary = {
  id: string;
  title: string;
  subtitle: string | null;
  tier: number;
  duration_minutes: number;
  environments: string[];
  intro: string;
};

export type AvailableListResponse = {
  items: ExpeditionSummary[];
};

export function listAvailableExpeditions(): Promise<AvailableListResponse> {
  return apiRequest<AvailableListResponse>("/v1/expeditions/available");
}

export type StartResponse = {
  expedition_id: string;
  started_at: string;
};

export function startExpedition(expeditionId: string): Promise<StartResponse> {
  return apiRequest<StartResponse>(`/v1/expeditions/${expeditionId}/start`, {
    method: "POST",
  });
}

export type ProgressItem = {
  expedition_id: string;
  title: string;
  started_at: string;
  completed_at: string | null;
  completed_step_count: number;
  total_step_count: number;
};

export type MyProgressResponse = {
  items: ProgressItem[];
};

export function listMyExpeditions(): Promise<MyProgressResponse> {
  return apiRequest<MyProgressResponse>("/v1/expeditions/me");
}
