import { getApiMeta } from "@/src/api/meta";

jest.mock("@/src/auth/token", () => ({
  getBearerToken: jest.fn(async () => "must-not-be-read"),
  getBearerTokenSnapshot: jest.fn(async () => ({ token: "must-not-be-read", generation: 0 })),
  bearerTokenSnapshotIsCurrent: jest.fn(() => true),
}));

describe("Observation capability metadata", () => {
  it("reads the public metadata endpoint without a bearer header", async () => {
    globalThis.fetch = jest.fn(async () => ({
      ok: true,
      status: 200,
      json: async () => ({
        name: "The Hinterland Guide",
        env: "dev",
        version: "test",
        capabilities: { observation: { photo_helper_enabled: false } },
      }),
    })) as unknown as typeof fetch;

    await expect(getApiMeta()).resolves.toMatchObject({
      capabilities: { observation: { photo_helper_enabled: false } },
    });
    expect(globalThis.fetch).toHaveBeenCalledWith(
      "http://jest.invalid/v1/meta",
      expect.objectContaining({ headers: expect.not.objectContaining({ Authorization: expect.anything() }) }),
    );
  });
});
