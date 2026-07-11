import {
  bootstrapParentSession,
  consumeParentRedirect,
  createParentMsalConfiguration,
  suggestAdultDisplayName,
} from "@/src/auth/msal";

describe("suggestAdultDisplayName", () => {
  it("uses a compact editable Microsoft account name without deriving from email", () => {
    expect(suggestAdultDisplayName("  Alex   Adult  ")).toBe("Alex Adult");
    expect(suggestAdultDisplayName(undefined)).toBe("");
  });

  it("fits the server's 80-character display-name contract", () => {
    expect(Array.from(suggestAdultDisplayName("🦋".repeat(81)))).toHaveLength(80);
  });

  it("uses the dedicated parent callback and its exact authority", () => {
    const config = createParentMsalConfiguration({
      clientId: "client-id",
      authority: "https://login.example.test/tenant",
      redirectUri: "https://parents.example.test/auth/callback",
    });

    expect(config.auth.redirectUri).toBe(
      "https://parents.example.test/auth/callback",
    );
    expect(config.auth.knownAuthorities).toEqual(["login.example.test"]);
  });

  it("consumes the redirect before activating its exact account", async () => {
    const account = { homeAccountId: "adult-account" };
    const handleRedirectPromise = jest.fn().mockResolvedValue({ account });
    const clearCache = jest.fn();
    const activateAccount = jest.fn();
    const beginLogout = jest.fn();
    const syncCachedAccount = jest.fn();

    await consumeParentRedirect(
      { clearCache, handleRedirectPromise } as never,
      { activateAccount, beginLogout, syncCachedAccount } as never,
    );

    expect(handleRedirectPromise).toHaveBeenCalledWith({
      navigateToLoginRequestUrl: true,
    });
    expect(activateAccount).toHaveBeenCalledWith(account);
    expect(handleRedirectPromise.mock.invocationCallOrder[0]).toBeLessThan(
      activateAccount.mock.invocationCallOrder[0],
    );
  });

  it("clears a stale adult and skips token publication after a failed callback", async () => {
    const handleRedirectPromise = jest
      .fn()
      .mockRejectedValue(new Error("provider response detail"));
    const clearCache = jest.fn().mockResolvedValue(undefined);
    const activateAccount = jest.fn();
    const beginLogout = jest.fn().mockResolvedValue(null);
    const syncCachedAccount = jest.fn();
    const beforeCachedAccountSync = jest.fn();
    const navigateAfterFailure = jest.fn();
    const scrubAfterFailure = jest.fn();

    const outcome = await bootstrapParentSession(
      { clearCache, handleRedirectPromise } as never,
      { activateAccount, beginLogout, syncCachedAccount } as never,
      beforeCachedAccountSync,
      navigateAfterFailure,
      scrubAfterFailure,
    );

    expect(outcome).toBe("failed");
    expect(beginLogout).toHaveBeenCalledTimes(1);
    expect(clearCache).toHaveBeenCalledTimes(1);
    expect(scrubAfterFailure).toHaveBeenCalledTimes(1);
    expect(navigateAfterFailure).toHaveBeenCalledTimes(1);
    expect(activateAccount).not.toHaveBeenCalled();
    expect(beforeCachedAccountSync).not.toHaveBeenCalled();
    expect(syncCachedAccount).not.toHaveBeenCalled();
  });

  it("does not leave the callback route when identity clearing fails", async () => {
    const navigateAfterFailure = jest.fn();
    const scrubAfterFailure = jest.fn();
    const outcome = await bootstrapParentSession(
      {
        handleRedirectPromise: jest.fn().mockRejectedValue(new Error("expired")),
        clearCache: jest.fn().mockRejectedValue(new Error("cache unavailable")),
      } as never,
      {
        activateAccount: jest.fn(),
        beginLogout: jest.fn().mockResolvedValue(null),
        syncCachedAccount: jest.fn(),
      } as never,
      jest.fn(),
      navigateAfterFailure,
      scrubAfterFailure,
    );

    expect(outcome).toBe("failed");
    expect(scrubAfterFailure).toHaveBeenCalledTimes(1);
    expect(navigateAfterFailure).not.toHaveBeenCalled();
  });

  it("keeps a pending or empty callback inert without clearing MSAL's response", async () => {
    const clearCache = jest.fn().mockResolvedValue(undefined);
    const beginLogout = jest.fn().mockResolvedValue(null);
    const syncCachedAccount = jest.fn();
    const scrubAfterFailure = jest.fn();

    const outcome = await bootstrapParentSession(
      {
        handleRedirectPromise: jest.fn().mockResolvedValue(null),
        clearCache,
      } as never,
      {
        activateAccount: jest.fn(),
        beginLogout,
        syncCachedAccount,
      } as never,
      jest.fn(),
      jest.fn(),
      scrubAfterFailure,
      () => true,
    );

    expect(outcome).toBe("callback_pending");
    expect(scrubAfterFailure).not.toHaveBeenCalled();
    expect(beginLogout).not.toHaveBeenCalled();
    expect(clearCache).not.toHaveBeenCalled();
    expect(syncCachedAccount).not.toHaveBeenCalled();
  });
});
