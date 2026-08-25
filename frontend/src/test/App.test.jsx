import { describe, it, expect, vi, afterEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import App from "../App";

// The boot path is what a first-time visitor actually experiences: a hosted
// backend may be waking up (models still loading) or unreachable entirely.
//
// Neither may cost the player a full-screen spinner on arrival. The welcome
// screen renders straight away and the wake-up, if there is one left to do,
// happens on the Play button while they read the rules.
function stubFetch(handler) {
  globalThis.fetch = vi.fn(handler);
}

const ok = (body) => Promise.resolve({ ok: true, status: 200, json: () => Promise.resolve(body) });

afterEach(() => {
  vi.restoreAllMocks();
});

describe("App boot states", () => {
  it("shows the welcome screen immediately, even while the models load", async () => {
    stubFetch(() => ok({ status: "ok", models_loaded: false, languages: [] }));
    render(<App />);
    expect(await screen.findByRole("button", { name: /בואו נשחק/ })).toBeInTheDocument();
    expect(screen.queryByText(/טוען מודלי שפה/)).not.toBeInTheDocument();
  });

  it("shows the welcome screen even when the server is unreachable", async () => {
    // No dead spinner: an unreachable backend is indistinguishable from a sleeping
    // one at this point, and either way the rules are worth reading.
    stubFetch(() => Promise.reject(new Error("network down")));
    render(<App />);
    expect(await screen.findByRole("button", { name: /בואו נשחק/ })).toBeInTheDocument();
  });

  it("waits on the Play button when the language isn't loaded yet", async () => {
    // Hebrew loads before English, so readiness is per language: asking to play
    // Hebrew must not wait out the English load.
    const user = userEvent.setup();
    let heReady = false;
    stubFetch((url) => {
      const u = String(url);
      if (u.includes("/health")) {
        return ok({ status: "ok", models_loaded: false, languages: heReady ? ["he"] : [] });
      }
      if (u.includes("/pair")) return ok({ word1: "שמש", word2: "ירח", language: "he" });
      return ok({ valid: true, canonical: "", language: "he", in_vocab: true, suggestions: [] });
    });
    render(<App />);

    await user.click(await screen.findByRole("button", { name: /בואו נשחק/ }));
    expect(await screen.findByRole("button", { name: /מעירים את השרת/ })).toBeInTheDocument();

    heReady = true;
    // Once Hebrew is in, the game starts on its own — no second click.
    expect(await screen.findByRole("textbox", {}, { timeout: 10000 })).toBeInTheDocument();
  }, 15000);

  it("lets a player abandon a long game without reloading the page", async () => {
    // Measured: ~6% of games run past 20 rounds. Until this existed, the only way
    // out of one was a page reload.
    const user = userEvent.setup();
    stubFetch((url) => {
      const u = String(url);
      if (u.includes("/health")) return ok({ status: "ok", models_loaded: true });
      if (u.includes("/pair")) return ok({ word1: "fire", word2: "ice", language: "en" });
      return ok({ valid: true, canonical: "", language: "en", in_vocab: true, suggestions: [] });
    });
    render(<App />);

    // The welcome screen defaults to Hebrew; switch so the whole flow is English.
    await user.click(await screen.findByRole("button", { name: /English/ }));
    await user.click(screen.getByRole("button", { name: /Let's Play/ }));
    // In a round now: the guess box is showing.
    expect(await screen.findByRole("textbox")).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: /New game/ }));
    // Back at the welcome screen, ready to start over.
    expect(await screen.findByRole("button", { name: /Let's Play/ })).toBeInTheDocument();
  });

  it("surfaces an error when starting a game fails", async () => {
    // Health is fine, but /pair fails — the Play button used to just stop
    // spinning with no explanation.
    stubFetch((url) => {
      if (String(url).includes("/health")) return ok({ status: "ok", models_loaded: true });
      return Promise.resolve({ ok: false, status: 500, json: () => Promise.resolve({ detail: "boom" }) });
    });
    render(<App />);

    const user = userEvent.setup();
    const play = await screen.findByRole("button", { name: /בואו נשחק/ });
    await user.click(play);
    await waitFor(() => expect(screen.getByRole("alert")).toHaveTextContent(/לא הצלחנו להתחיל משחק/));
  });
});
