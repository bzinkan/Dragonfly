import { env } from "@/src/config/env";

export type HealthResponse = {
  status: string;
  env: string;
  version: string;
};

export async function fetchHealth(signal?: AbortSignal): Promise<HealthResponse> {
  const res = await fetch(`${env.apiBaseUrl}/health`, { signal });
  if (!res.ok) {
    throw new Error(`/health returned HTTP ${res.status}`);
  }
  return (await res.json()) as HealthResponse;
}
