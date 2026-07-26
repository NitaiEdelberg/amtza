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

export default function GuessInput({ onSubmit, disabled, currentPair, isLoading }) {
  const [value, setValue] = useState("");
  const [validation, setValidation] = useState(null); // null | {valid, canonical}
  const [validating, setValidating] = useState(false);
  const inputRef = useRef(null);
  const debouncedValue = useDebounce(value, 300);

  useEffect(() => {
    setValue("");
    setValidation(null);
    if (inputRef.current) inputRef.current.focus();
  }, [currentPair]);

  useEffect(() => {
    if (debouncedValue.length < 2) {
      setValidation(null);
      return;
    }
    setValidating(true);
    validateWord(debouncedValue)
      .then((res) => setValidation(res))
      .catch(() => setValidation({ valid: false }))
      .finally(() => setValidating(false));
  }, [debouncedValue]);

  const isHebrew = currentPair?.language === "he";
  const pairWords = [
    currentPair?.word1?.toLowerCase(),
    currentPair?.word2?.toLowerCase(),
  ];
  const isSameAsPair = validation?.canonical && pairWords.includes(validation.canonical.toLowerCase());
  const canSubmit =
    !disabled && !isLoading && value.trim().length > 0 &&
    validation?.valid && !isSameAsPair;

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
    } else if (validation?.valid === false) {
      statusClass = "invalid";
      statusMsg = isHebrew ? "המילה לא נמצאה במילון 🤔" : "Word not found in dictionary 🤔";
    } else if (validation?.valid === true) {
      statusClass = "valid";
    }
  }

  return (
    <form className="guess-input" onSubmit={handleSubmit}>
      <div className={`guess-input__field guess-input__field--${statusClass}`}>
        <input
          ref={inputRef}
          dir="auto"
          type="text"
          value={value}
          onChange={(e) => setValue(e.target.value)}
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
      {statusMsg && <p className="guess-input__status">{statusMsg}</p>}
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
