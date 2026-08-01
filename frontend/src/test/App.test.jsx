import { describe, it, expect, vi, afterEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import App from "../App";

// The boot path is what a first-time visitor actually experiences: a hosted
// backend may be waking up (models_loaded false) or unreachable entirely. Both
// used to look identical — an endless "loading models" spinner.
function stubFetch(handler) {
  globalThis.fetch = vi.fn(handler);
}

const ok = (body) => Promise.resolve({ ok: true, status: 200, json: () => Promise.resolve(body) });

afterEach(() => {
  vi.restoreAllMocks();
});

describe("App boot states", () => {
  it("shows the loading screen until the models are ready", async () => {
    stubFetch(() => ok({ status: "ok", models_loaded: false }));
    render(<App />);
    expect(await screen.findByText(/טוען מודלי שפה/)).toBeInTheDocument();
  });

  it("moves to the welcome screen once the models load", async () => {
    stubFetch(() => ok({ status: "ok", models_loaded: true }));
    render(<App />);
    expect(await screen.findByRole("button", { name: /בואו נשחק/ })).toBeInTheDocument();
  });

  it("reports an unreachable server instead of spinning forever", async () => {
    // Every poll fails; after several consecutive failures the UI should say so
    // and offer a retry rather than claiming models are loading.
    stubFetch(() => Promise.reject(new Error("network down")));
    render(<App />);

    expect(
      await screen.findByText(/אין חיבור לשרת/, {}, { timeout: 20000 })
    ).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /נסו שוב/ })).toBeInTheDocument();
  }, 25000);

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
