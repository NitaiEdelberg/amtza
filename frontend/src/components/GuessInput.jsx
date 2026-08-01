import { useState, useEffect, useRef } from "react";
import { validateWord } from "../api";

function useDebounce(value, delay) {
  const [debounced, setDebounced] = useState(value);
  useEffect(() => {
    const t = setTimeout(() => setDebounced(value), delay);
    return () => clearTimeout(t);
  }, [value, delay]);
  return debounced;
}

export default function GuessInput({ onSubmit, disabled, currentPair, isLoading, error, onClearError }) {
  const [value, setValue] = useState("");
  const [validation, setValidation] = useState(null); // null | {word, valid, canonical, in_vocab, suggestions}
  const inputRef = useRef(null);
  const debouncedValue = useDebounce(value, 300);

  // NOTE: this component is mounted with a key derived from the current pair (see
  // GameBoard), so a new round remounts it and the input/validation reset
  // naturally — no effect needed to clear state when the pair changes.

  // Typing again means the player has moved on from the last rejection. Done in
  // the change handler rather than an effect — it's a reaction to an event, not
  // synchronised state.
  function handleChange(e) {
    setValue(e.target.value);
    if (error) onClearError?.();
  }

  function applySuggestion(word) {
    setValue(word);
    onClearError?.();
    inputRef.current?.focus();
  }

  // Each result is tagged with the word it describes. Responses can land out of
  // order (or after the player has typed on), and acting on a stale one would
  // enable Submit for a word the server never approved.
  useEffect(() => {
    const word = debouncedValue.trim();
    if (word.length < 2) return;
    let cancelled = false;
    validateWord(word)
      .then((res) => { if (!cancelled) setValidation({ ...res, word }); })
      .catch(() => { if (!cancelled) setValidation({ valid: false, word }); });
    return () => { cancelled = true; };
  }, [debouncedValue]);

  const isHebrew = currentPair?.language === "he";
  const pairWords = [
    currentPair?.word1?.toLowerCase(),
    currentPair?.word2?.toLowerCase(),
  ];
  // Only trust a result that describes exactly what's in the box right now.
  const checked = validation?.word === value.trim() ? validation : null;
  // Derived rather than stored: we're waiting exactly while the debounced word is
  // long enough to check but has no matching result yet.
  const validating =
    debouncedValue.trim().length >= 2 && validation?.word !== debouncedValue.trim();
  const isSameAsPair = checked?.canonical && pairWords.includes(checked.canonical.toLowerCase());
  const canSubmit =
    !disabled && !isLoading && value.trim().length > 0 &&
    checked?.valid && !isSameAsPair;

  function handleSubmit(e) {
    e.preventDefault();
    if (!canSubmit) return;
    onSubmit(value.trim());
  }

  let statusClass = "";
  let statusMsg = "";
  if (value.length >= 2 && !validating) {
    if (isSameAsPair) {
      statusClass = "invalid";
      statusMsg = isHebrew ? "המילה כבר בזוג הנוכחי" : "Word already in current pair";
    } else if (checked?.valid === false) {
      statusClass = "invalid";
      statusMsg = isHebrew ? "המילה לא נמצאה במילון 🤔" : "Word not found in dictionary 🤔";
    } else if (checked?.in_vocab === false) {
      // Spelled plausibly, but the model has no vector for it — warn now rather
      // than letting the player submit and get rejected.
      statusClass = "warn";
      statusMsg = isHebrew ? "המילה לא במילון של המשחק" : "Not in the game's dictionary";
    } else if (checked?.valid === true) {
      statusClass = "valid";
    }
  }

  // Alternatives worth offering: from the live check, or from a rejected submit.
  const suggestions = (error?.suggestions?.length ? error.suggestions : checked?.suggestions) || [];
  const showSuggestions = suggestions.length > 0 && (statusClass === "warn" || error);

  return (
    <form className="guess-input" onSubmit={handleSubmit}>
      <div className={`guess-input__field guess-input__field--${statusClass}`}>
        <input
          ref={inputRef}
          autoFocus
          dir="auto"
          type="text"
          value={value}
          onChange={handleChange}
          // A placeholder is not an accessible name — it disappears on input.
          aria-label={isHebrew ? "הניחוש שלכם" : "Your guess"}
          placeholder={isHebrew ? "כתבו מילה..." : "type a word..."}
          disabled={disabled || isLoading}
          autoComplete="off"
          autoCorrect="off"
          spellCheck={false}
        />
        {validating && <span className="guess-input__spinner">⟳</span>}
        {!validating && statusClass === "valid" && <span className="guess-input__icon valid">✓</span>}
        {!validating && statusClass === "invalid" && <span className="guess-input__icon invalid">✗</span>}
      </div>
      {statusMsg && (
        <p className={`guess-input__status guess-input__status--${statusClass}`}>{statusMsg}</p>
      )}

      {error && (
        <p className="guess-input__error" role="alert">{error.message}</p>
      )}

      {showSuggestions && (
        <div className="guess-input__suggestions">
          <span className="guess-input__suggestions-label">
            {isHebrew ? "אולי התכוונתם ל־" : "Did you mean"}
          </span>
          {suggestions.map((w) => (
            <button
              key={w}
              type="button"
              className="guess-input__suggestion"
              onClick={() => applySuggestion(w)}
            >
              {w}
            </button>
          ))}
        </div>
      )}

      <button
        type="submit"
        className="btn btn--primary"
        disabled={!canSubmit}
      >
        {isLoading
          ? (isHebrew ? "חושב..." : "thinking...")
          : (isHebrew ? "שלח ניחוש 🎯" : "Submit guess 🎯")}
      </button>
    </form>
  );
}
