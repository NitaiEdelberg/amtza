import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import WinScreen from "../components/WinScreen";

// Confetti paints to a canvas, which jsdom doesn't implement — and it isn't what
// we're testing.
vi.mock("react-confetti", () => ({ default: () => null }));

const history = [
  {
    word1: "fire", word2: "ice",
    player_guess: "steam", computer_guess: "frost",
    player_similarity: 0.4, computer_similarity: 0.5, player_computer_similarity: 0.3,
    language: "en",
  },
];

function renderWin(props = {}) {
  return render(
    <WinScreen
      winMessage="We did it! 🎉 Found the middle!"
      rounds={3}
      playerWord="marsh"
      computerWord="marsh"
      history={history}
      onNewGame={() => {}}
      language="en"
      {...props}
    />
  );
}

describe("WinScreen", () => {
  it("shows the win message", () => {
    renderWin();
    expect(screen.getByText(/Found the middle/)).toBeInTheDocument();
  });

  it("shows a single word when both sides said the same thing", () => {
    renderWin({ playerWord: "marsh", computerWord: "marsh" });
    expect(screen.getByText("marsh")).toBeInTheDocument();
    expect(screen.queryByText("≈")).not.toBeInTheDocument();
  });

  it("shows both words when the win was on similarity, not an exact match", () => {
    // The player must be able to see the two words weren't identical — this is
    // the screen that would otherwise imply "brother" and "father" were the same.
    renderWin({ playerWord: "brother", computerWord: "father" });
    expect(screen.getByText("brother")).toBeInTheDocument();
    expect(screen.getByText("father")).toBeInTheDocument();
    expect(screen.getByText("≈")).toBeInTheDocument();
  });

  it("treats a case difference as the same word", () => {
    renderWin({ playerWord: "Marsh", computerWord: "marsh" });
    expect(screen.queryByText("≈")).not.toBeInTheDocument();
  });

  it("pluralises the round count", () => {
    renderWin({ rounds: 1 });
    expect(screen.getByText(/Met in the middle in 1 round!/)).toBeInTheDocument();
  });

  it("uses Hebrew copy for a Hebrew game", () => {
    renderWin({ language: "he", rounds: 2 });
    expect(screen.getByRole("button", { name: /משחק חדש/ })).toBeInTheDocument();
  });

  it("offers a new game", async () => {
    const onNewGame = vi.fn();
    renderWin({ onNewGame });
    screen.getByRole("button", { name: /New Game/ }).click();
    expect(onNewGame).toHaveBeenCalled();
  });
});

describe("share text", () => {
  it("shows the starting pair and one square per round, not the answer", async () => {
    const { shareText } = await import("../share");
    const history = [
      { word1: "עץ", word2: "תפוח", player_guess: "ירוק", computer_guess: "אגס", player_computer_similarity: 0.2, is_won: false },
      { word1: "ירוק", word2: "אגס", player_guess: "פרי", computer_guess: "פרי", player_computer_similarity: 1, is_won: true },
    ];
    const text = shareText(history, "he", "https://amtza.netlify.app");
    expect(text).toContain("עץ + תפוח");
    expect(text).toContain("🟥🟩");
    expect(text).toContain("בסיבוב 2");
    expect(text).toContain("https://amtza.netlify.app");
    expect(text).not.toContain("פרי");
  });
});
