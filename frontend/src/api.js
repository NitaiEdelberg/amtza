const BASE_URL = import.meta.env.VITE_API_URL || "http://localhost:8000";

// The free backend has 0.1 of a CPU. Under a crowd a request can queue for
// seconds, and a request that never answers used to leave the button spinning
// forever. Every game call now gives up after REQUEST_TIMEOUT_MS and is retried
// once if the failure looks transient. That is safe because the server keeps no
// game state: sending the same guess twice gives the same answer.
const REQUEST_TIMEOUT_MS = 15000;
const RETRY_DELAY_MS = 1500;

function transientError(code, status) {
  const error = new Error(code);
  error.code = code;
  error.status = status;
  error.suggestions = [];
  return error;
}

async function fetchWithTimeout(url, options = {}) {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), REQUEST_TIMEOUT_MS);
  try {
    return await fetch(url, { ...options, signal: controller.signal });
  } catch (e) {
    throw transientError(e?.name === "AbortError" ? "timeout" : "network");
  } finally {
    clearTimeout(timer);
  }
}

/** fetch + parse, retrying once on a timeout, a dropped connection or a 5xx.
 *
 * Never retries a 4xx: those are answers (an unknown word, "slow down"), and
 * repeating them would only add load.
 */
async function request(url, options) {
  for (let attempt = 0; ; attempt++) {
    try {
      const res = await fetchWithTimeout(url, options);
      if (res.status >= 500) throw transientError("server_busy", res.status);
      return await handleResponse(res);
    } catch (e) {
      const transient = ["timeout", "network", "server_busy"].includes(e.code);
      if (!transient || attempt >= 1) throw e;
      await new Promise((r) => setTimeout(r, RETRY_DELAY_MS));
    }
  }
}

async function handleResponse(res) {
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: "Network error" }));
    const detail = err.detail;
    const isObj = detail && typeof detail === "object";
    const message = isObj ? detail.message : detail;
    const error = new Error(message || `HTTP ${res.status}`);
    // Keep the structured parts so the UI can react — notably `suggestions`,
    // which turns "word not found" from a dead end into something clickable.
    error.status = res.status;
    error.code = isObj ? detail.error : undefined;
    error.suggestions = (isObj && detail.suggestions) || [];
    throw error;
  }
  return res.json();
}

export async function checkHealth() {
  const res = await fetch(`${BASE_URL}/health`);
  return res.json();
}

/** Resolve once `lang` is playable, or false if it never becomes ready.
 *
 * Readiness is per language: the backend loads Hebrew first, so a Hebrew game can
 * start while English is still streaming in. Older backends don't send
 * `languages`, so fall back to the global flag.
 */
export async function waitForLanguage(lang, { timeoutMs = 180000, onTick } = {}) {
  const startedAt = Date.now();
  let consecutiveErrors = 0;
  while (Date.now() - startedAt < timeoutMs) {
    try {
      const health = await checkHealth();
      consecutiveErrors = 0;
      if (health.languages ? health.languages.includes(lang) : health.models_loaded) {
        return true;
      }
    } catch {
      consecutiveErrors += 1;
    }
    onTick?.({
      seconds: Math.round((Date.now() - startedAt) / 1000),
      unreachable: consecutiveErrors >= 4,
    });
    await new Promise((r) => setTimeout(r, 2000));
  }
  return false;
}

export async function getRandomPair(lang = null) {
  const url = lang ? `${BASE_URL}/pair?lang=${lang}` : `${BASE_URL}/pair`;
  return request(url);
}

export async function submitGuess(word1, word2, playerGuess, roundNum, usedWords = [], gameId = null) {
  return request(`${BASE_URL}/guess`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      word1, word2, player_guess: playerGuess, round_num: roundNum, used_words: usedWords,
      game_id: gameId,
    }),
  });
}

/** A fresh random id per game. Groups a game's rounds in the anonymous log;
 * it is never stored on the device, so it can't link one game to the next. */
export function newGameId() {
  return globalThis.crypto?.randomUUID?.() ?? null;
}

export async function validateWord(word) {
  return handleResponse(await fetch(`${BASE_URL}/validate/${encodeURIComponent(word)}`));
}

export async function getHint(word1, word2) {
  return request(`${BASE_URL}/hint`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ word1, word2 }),
  });
}

/** Player-facing text for failures that aren't about the word itself. */
export function friendlyError(err, isHe) {
  if (err?.code === "rate_limited" || err?.status === 429) {
    return isHe ? "רגע, יותר מדי ניחושים ברצף. נסו שוב בעוד כמה שניות"
                : "Too many guesses in a row. Try again in a few seconds";
  }
  if (["timeout", "network", "server_busy"].includes(err?.code)) {
    return isHe ? "השרת עמוס כרגע, הרבה אנשים משחקים. נסו שוב בעוד רגע"
                : "The server is busy right now, lots of people are playing. Try again in a moment";
  }
  return err?.message;
}
