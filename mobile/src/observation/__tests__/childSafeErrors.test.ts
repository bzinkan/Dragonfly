import { ApiError } from "@/src/api/client";
import {
  childSafeError,
  isEntryUnavailableError,
} from "@/src/observation/childSafeErrors";

function apiError(status: number, requestId = "req-safe-1") {
  return new ApiError(
    status,
    { error: { code: "raw_code", message: "raw server text", request_id: requestId } },
    "raw server text",
  );
}

describe("child-safe Observation errors", () => {
  it("never exposes raw server or HTTP text", () => {
    for (const status of [401, 403, 404, 409, 422, 500, 503]) {
      const safe = childSafeError(apiError(status));
      expect(safe.message).not.toContain("raw");
      expect(safe.message).not.toContain(String(status));
      expect(safe.supportCode).toBe("req-safe-1");
    }
    expect(childSafeError(new Error("socket secret detail")).message).not.toContain("socket");
  });

  it("distinguishes auth, unavailable, conflict, and retryable failures", () => {
    expect(childSafeError(apiError(401))).toMatchObject({ requiresAdultHandoff: true });
    expect(childSafeError(apiError(404)).message).toContain("isn’t available");
    expect(childSafeError(apiError(409))).toMatchObject({ requiresAdultHandoff: true });
    expect(childSafeError(apiError(503)).message).toContain("saved work is safe");
  });

  it("marks only authorization/not-found detail failures as stale-image removal", () => {
    expect(isEntryUnavailableError(apiError(403))).toBe(true);
    expect(isEntryUnavailableError(apiError(404))).toBe(true);
    expect(isEntryUnavailableError(apiError(409))).toBe(false);
    expect(isEntryUnavailableError(new Error("network"))).toBe(false);
  });
});
