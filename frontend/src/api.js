const BASE_URL = import.meta.env.VITE_API_URL || "http://localhost:8000";

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

export async function getRandomPair(lang = null) {
  const url = lang ? `${BASE_URL}/pair?lang=${lang}` : `${BASE_URL}/pair`;
  return handleResponse(await fetch(url));
}

export async function submitGuess(word1, word2, playerGuess, roundNum, usedWords = []) {
  return handleResponse(
    await fetch(`${BASE_URL}/guess`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ word1, word2, player_guess: playerGuess, round_num: roundNum, used_words: usedWords }),
    })
  );
}

export async function validateWord(word) {
  return handleResponse(await fetch(`${BASE_URL}/validate/${encodeURIComponent(word)}`));
}

export async function getHint(word1, word2) {
  return handleResponse(
    await fetch(`${BASE_URL}/hint`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ word1, word2 }),
    })
  );
}
