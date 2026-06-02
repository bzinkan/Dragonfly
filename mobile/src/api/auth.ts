import { apiRequest } from "@/src/api/client";

export type UserResponse = {
  id: string;
  /**
   * Entra External Identities object id for adult accounts, replaces
   * the Phase 5 `firebase_uid` field after the Phase 6a auth swap.
   * Null for kid accounts (kids have no Entra identity).
   */
  entra_oid: string | null;
  role: string;
  display_name: string;
};

export type CurrentUser = {
  id: string;
  entra_oid: string | null;
  role: string;
  display_name: string;
};

export function parentSignup(displayName: string): Promise<UserResponse> {
  return apiRequest<UserResponse>("/v1/auth/parent-signup", {
    method: "POST",
    body: { display_name: displayName },
  });
}

export function getMe(): Promise<CurrentUser> {
  return apiRequest<CurrentUser>("/v1/me");
}

export type KidExchangeResponse = {
  session_token: string;
  expires_at: string;
  user: {
    id: string;
    role: string;
    display_name: string;
  };
};

/**
 * Exchange a kid handoff JWT (15-min single-use) for a 30-day session JWT.
 * Public endpoint -- the handoff token IS the auth.
 */
export function kidExchange(handoffToken: string): Promise<KidExchangeResponse> {
  return apiRequest<KidExchangeResponse>("/v1/auth/kid-exchange", {
    method: "POST",
    body: { handoff_token: handoffToken },
    unauthenticated: true,
  });
}
