import { ApiError } from "@/src/api/client";

export type ChildSafeError = {
  message: string;
  supportCode: string | null;
  requiresAdultHandoff: boolean;
};

const OFFLINE_MESSAGE =
  "Your saved work is safe. We’ll try again when the connection is ready.";

export function isEntryUnavailableError(error: unknown): boolean {
  return error instanceof ApiError && (error.status === 403 || error.status === 404);
}

/** Never pass server/proxy/network error text through to a child surface. */
export function childSafeError(error: unknown): ChildSafeError {
  if (error instanceof ApiError) {
    const supportCode = error.body?.error.request_id ?? null;
    if (error.status === 401) {
      return {
        message: "Your session needs an adult handoff before you can continue.",
        supportCode,
        requiresAdultHandoff: true,
      };
    }
    if (error.status === 403 || error.status === 404) {
      return {
        message: "This Field Journal entry isn’t available.",
        supportCode,
        requiresAdultHandoff: false,
      };
    }
    if (error.status === 409) {
      return {
        message: "An adult needs to help finish this update.",
        supportCode,
        requiresAdultHandoff: true,
      };
    }
    return {
      message: error.status >= 500 ? OFFLINE_MESSAGE : "That didn’t work. Please try again.",
      supportCode,
      requiresAdultHandoff: false,
    };
  }
  return {
    message: OFFLINE_MESSAGE,
    supportCode: null,
    requiresAdultHandoff: false,
  };
}
