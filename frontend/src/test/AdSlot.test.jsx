import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import AdSlot from "../components/AdSlot";
import GameBoard from "../components/GameBoard";

// The build ships with no publisher ID, so the slot must be completely inert:
// no markup, no third-party script, no reserved gap in the layout. Everything
// here runs in that default state, which is also the state the game is in until
// AdSense approves an account.
describe("AdSlot without a publisher ID", () => {
  it("renders nothing at all", () => {
    const { container } = render(<AdSlot label="Advertisement" />);
    expect(container).toBeEmptyDOMElement();
  });

  it("does not load the AdSense script", () => {
    render(<AdSlot label="Advertisement" />);
    const scripts = [...document.querySelectorAll("script")].map((s) => s.src);
    expect(scripts.some((s) => s.includes("googlesyndication"))).toBe(false);
  });
});

describe("ad placement in a game", () => {
  const pair = { word1: "cat", word2: "dog", language: "en" };
  const props = {
    gamePhase: "guessing",
    currentPair: pair,
    lastRound: null,
    history: [],
    onGuess: () => {},
    onNextRound: () => {},
    isLoading: false,
    onGetHint: () => {},
    hintWords: [],
    hintUsed: false,
    guessError: null,
    onClearGuessError: () => {},
    onNewGame: () => {},
  };

  it("keeps the first round ad-free", () => {
    render(<GameBoard {...props} roundNum={1} />);
    expect(screen.queryByLabelText("Advertisement")).not.toBeInTheDocument();
  });

  it("still renders the board normally from round two", () => {
    // With no publisher ID the slot is absent either way; what must hold is that
    // reaching round two doesn't disturb the game itself.
    render(<GameBoard {...props} roundNum={2} />);
    expect(screen.getByRole("textbox")).toBeInTheDocument();
  });
});
