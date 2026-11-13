import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { submitGuess, friendlyError } from "../api";

const ok = (body) => ({ ok: true, status: 200, json: async () => body });
const fail = (status, detail) => ({ ok: false, status, json: async () => ({ detail }) });

describe("api client under a busy server", () => {
  beforeEach(() => vi.useFakeTimers());
  afterEach(() => {
    vi.useRealTimers();
    vi.unstubAllGlobals();
  });

  it("retries a 5xx once and returns the second answer", async () => {
    const fetchMock = vi.fn()
      .mockResolvedValueOnce(fail(503, "busy"))
      .mockResolvedValueOnce(ok({ computer_guess: "fruit" }));
    vi.stubGlobal("fetch", fetchMock);
    const p = submitGuess("apple", "tree", "fruit", 1);
    await vi.advanceTimersByTimeAsync(2000);
    await expect(p).resolves.toEqual({ computer_guess: "fruit" });
    expect(fetchMock).toHaveBeenCalledTimes(2);
  });

  it("gives up after the retry with a server_busy error", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(fail(502, "bad gateway")));
    const p = submitGuess("apple", "tree", "fruit", 1);
    const settled = expect(p).rejects.toMatchObject({ code: "server_busy" });
    await vi.advanceTimersByTimeAsync(2000);
    await settled;
  });

  it("never retries a 4xx: unknown words and 'slow down' are answers", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      fail(429, { error: "rate_limited", message: "Too many requests." })
    );
    vi.stubGlobal("fetch", fetchMock);
    await expect(submitGuess("a", "b", "c", 1)).rejects.toMatchObject({ code: "rate_limited" });
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });

  it("times out a request that never answers, then retries it", async () => {
    const fetchMock = vi.fn((url, { signal }) => new Promise((_, reject) => {
      signal.addEventListener("abort", () => reject(Object.assign(new Error("aborted"), { name: "AbortError" })));
    }));
    vi.stubGlobal("fetch", fetchMock);
    const p = submitGuess("a", "b", "c", 1);
    const settled = expect(p).rejects.toMatchObject({ code: "timeout" });
    await vi.advanceTimersByTimeAsync(40000);
    await settled;
    expect(fetchMock).toHaveBeenCalledTimes(2);
  });
});

describe("friendlyError", () => {
  it("speaks the game's language for busy and rate-limited", () => {
    expect(friendlyError({ code: "rate_limited" }, true)).toMatch(/יותר מדי/);
    expect(friendlyError({ code: "timeout" }, false)).toMatch(/busy/);
  });

  it("passes word errors through untouched", () => {
    expect(friendlyError({ code: "word_not_found", message: "Word 'x' not found" }, false))
      .toBe("Word 'x' not found");
  });
});
