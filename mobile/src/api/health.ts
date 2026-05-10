import { apiRequest } from "@/src/api/client";

export type HealthResponse = {
  status: string;
  env: string;
  version: string;
};

export function fetchHealth(signal?: AbortSignal): Promise<HealthResponse> {
  return apiRequest<HealthResponse>("/health", { unauthenticated: true, signal });
}
