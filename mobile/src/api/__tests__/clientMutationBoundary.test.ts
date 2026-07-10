import * as SecureStore from "expo-secure-store";

import { ApiError, apiRequest } from "@/src/api/client";
import { ImperativeRequestSupersededError } from "@/src/auth/requestBoundary";
import { setBearerToken } from "@/src/auth/token";

jest.mock("expo-secure-store", () => ({
  getItemAsync: jest.fn(),
  setItemAsync: jest.fn(),
  deleteItemAsync: jest.fn(),
}));

const getItemAsync = SecureStore.getItemAsync as jest.MockedFunction<
  typeof SecureStore.getItemAsync
>;
const setItemAsync = SecureStore.setItemAsync as jest.MockedFunction<
  typeof SecureStore.setItemAsync
>;
const deleteItemAsync = SecureStore.deleteItemAsync as jest.MockedFunction<
  typeof SecureStore.deleteItemAsync
>;

function deferred<T>() {
  let resolve!: (value: T) => void;
  const promise = new Promise<T>((done) => {
    resolve = done;
  });
  return { promise, resolve };
}

async function flushUntil(predicate: () => boolean): Promise<void> {
  for (let attempt = 0; attempt < 20 && !predicate(); attempt += 1) {
    await Promise.resolve();
  }
  expect(predicate()).toBe(true);
}

describe("global authenticated mutation boundary", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    getItemAsync.mockResolvedValue("old-token");
    setItemAsync.mockResolvedValue();
    globalThis.fetch = jest.fn(async () => ({
      ok: true,
      status: 200,
      json: async () => ({ saved: true }),
    })) as unknown as typeof fetch;
  });

  it("rejects an unwrapped POST when a token switch starts during SecureStore read", async () => {
    const read = deferred<string | null>();
    getItemAsync.mockReturnValueOnce(read.promise);
    const request = apiRequest<{ saved: boolean }>("/v1/write", {
      method: "POST",
      body: { value: 1 },
    });
    await flushUntil(() => getItemAsync.mock.calls.length === 1);

    await setBearerToken("new-token");
    read.resolve("old-token");

    await expect(request).rejects.toBeInstanceOf(
      ImperativeRequestSupersededError,
    );
    expect(globalThis.fetch).not.toHaveBeenCalled();
  });

  it("rejects a POST that begins while the token write is still pending", async () => {
    const write = deferred<void>();
    setItemAsync.mockReturnValueOnce(write.promise);
    const tokenChange = setBearerToken("new-token");
    const request = apiRequest<{ saved: boolean }>("/v1/write", {
      method: "POST",
    });

    write.resolve();
    await tokenChange;

    await expect(request).rejects.toBeInstanceOf(
      ImperativeRequestSupersededError,
    );
    expect(globalThis.fetch).not.toHaveBeenCalled();
  });

  it("keeps caller-driven GET cancellation intact", async () => {
    const controller = new AbortController();
    await apiRequest<{ ok: boolean }>("/v1/read", {
      signal: controller.signal,
    });

    expect(globalThis.fetch).toHaveBeenCalledWith(
      "http://jest.invalid/v1/read",
      expect.objectContaining({ signal: controller.signal }),
    );
  });

  it("clears the current authenticated session on a 401", async () => {
    globalThis.fetch = jest.fn(async () => ({
      ok: false,
      status: 401,
      json: async () => ({
        error: { code: "unauthorized", message: "raw", request_id: "req-401" },
      }),
    })) as unknown as typeof fetch;

    await expect(apiRequest("/v1/private")).rejects.toBeInstanceOf(ApiError);
    expect(deleteItemAsync).toHaveBeenCalledTimes(1);
  });

  it("does not let a late 401 from an old token erase a replacement", async () => {
    const response = deferred<any>();
    globalThis.fetch = jest.fn(() => response.promise) as unknown as typeof fetch;
    const request = apiRequest("/v1/private");
    await flushUntil(() => (globalThis.fetch as jest.Mock).mock.calls.length === 1);

    await setBearerToken("replacement-token");
    response.resolve({
      ok: false,
      status: 401,
      json: async () => ({
        error: { code: "unauthorized", message: "raw", request_id: "late-401" },
      }),
    });

    await expect(request).rejects.toBeInstanceOf(ApiError);
    expect(deleteItemAsync).not.toHaveBeenCalled();
  });
});
