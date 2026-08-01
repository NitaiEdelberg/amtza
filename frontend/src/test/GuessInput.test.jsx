import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import GuessInput from "../components/GuessInput";

// GuessInput validates against the API as you type. Stub fetch so the component's
// behaviour is what's under test, not the network.
function stubValidate(response) {
  globalThis.fetch = vi.fn(() =>
    Promise.resolve({ ok: true, status: 200, json: () => Promise.resolve(response) })
  );
}

const hebrewPair = { word1: "שבת", word2: "קפה", language: "he" };

beforeEach(() => {
  stubValidate({ valid: true, canonical: "", language: "he", in_vocab: true, suggestions: [] });
});
afterEach(() => {
  vi.restoreAllMocks();
});

describe("GuessInput", () => {
  it("disables submit until a valid word is typed", async () => {
    render(<GuessInput onSubmit={() => {}} currentPair={hebrewPair} />);
    expect(screen.getByRole("button", { name: /שלח ניחוש/ })).toBeDisabled();
  });

  it("submits the typed word", async () => {
    const user = userEvent.setup();
    const onSubmit = vi.fn();
    stubValidate({ valid: true, canonical: "בוקר", language: "he", in_vocab: true, suggestions: [] });
    render(<GuessInput onSubmit={onSubmit} currentPair={hebrewPair} />);

    await user.type(screen.getByRole("textbox"), "בוקר");
    const btn = screen.getByRole("button", { name: /שלח ניחוש/ });
    await waitFor(() => expect(btn).toBeEnabled());
    await user.click(btn);
    expect(onSubmit).toHaveBeenCalledWith("בוקר");
  });

  it("blocks a word that is already one of the pair words", async () => {
    const user = userEvent.setup();
    stubValidate({ valid: true, canonical: "שבת", language: "he", in_vocab: true, suggestions: [] });
    render(<GuessInput onSubmit={() => {}} currentPair={hebrewPair} />);

    await user.type(screen.getByRole("textbox"), "שבת");
    expect(await screen.findByText(/כבר בזוג הנוכחי/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /שלח ניחוש/ })).toBeDisabled();
  });

  it("warns before submitting when the word has no vector, and offers alternatives", async () => {
    const user = userEvent.setup();
    stubValidate({
      valid: true, canonical: "תפוחח", language: "he",
      in_vocab: false, suggestions: ["תפוח", "תפוחי"],
    });
    render(<GuessInput onSubmit={() => {}} currentPair={hebrewPair} />);

    await user.type(screen.getByRole("textbox"), "תפוחח");
    expect(await screen.findByText(/לא במילון של המשחק/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "תפוח" })).toBeInTheDocument();
  });

  it("shows a rejected guess inline (not via alert) with clickable suggestions", async () => {
    const user = userEvent.setup();
    const error = { message: "המילה 'תפוחח' לא נמצאה במילון", suggestions: ["תפוח"] };
    render(
      <GuessInput onSubmit={() => {}} currentPair={hebrewPair} error={error} onClearError={() => {}} />
    );

    expect(screen.getByRole("alert")).toHaveTextContent("לא נמצאה במילון");

    // Clicking a suggestion puts it in the input, so the player can just submit.
    await user.click(screen.getByRole("button", { name: "תפוח" }));
    expect(screen.getByRole("textbox")).toHaveValue("תפוח");
  });

  it("clears the previous error once the player edits the input", async () => {
    const user = userEvent.setup();
    const onClearError = vi.fn();
    const error = { message: "nope", suggestions: [] };
    render(
      <GuessInput onSubmit={() => {}} currentPair={hebrewPair} error={error} onClearError={onClearError} />
    );
    await user.type(screen.getByRole("textbox"), "א");
    expect(onClearError).toHaveBeenCalled();
  });

  it("starts empty for a new round (GameBoard remounts it via key)", async () => {
    const user = userEvent.setup();
    const { rerender } = render(
      <GuessInput key="שבת|קפה" onSubmit={() => {}} currentPair={hebrewPair} />
    );
    await user.type(screen.getByRole("textbox"), "בוקר");
    expect(screen.getByRole("textbox")).toHaveValue("בוקר");

    // A new pair means a new key, i.e. a fresh component with empty state.
    rerender(
      <GuessInput
        key="בוקר|לילה"
        onSubmit={() => {}}
        currentPair={{ word1: "בוקר", word2: "לילה", language: "he" }}
      />
    );
    expect(screen.getByRole("textbox")).toHaveValue("");
  });

  it("uses English copy for an English pair", () => {
    render(<GuessInput onSubmit={() => {}} currentPair={{ word1: "fire", word2: "ice", language: "en" }} />);
    expect(screen.getByPlaceholderText("type a word...")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Submit guess/ })).toBeInTheDocument();
  });
});
