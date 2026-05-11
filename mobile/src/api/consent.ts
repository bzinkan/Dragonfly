import { apiRequest } from "@/src/api/client";

export type ConsentResponse = {
  recorded_at: string;
  policy_version: string;
};

export function recordConsent(email: string): Promise<ConsentResponse> {
  return apiRequest<ConsentResponse>("/v1/auth/consent", {
    method: "POST",
    body: { email },
    unauthenticated: true,
  });
}
