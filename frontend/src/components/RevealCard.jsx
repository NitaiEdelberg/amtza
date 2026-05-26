import { useEffect, useState } from "react";

function isHebrew(text) {
  return /[֐-׿]/.test(text ?? "");
}

function FlipCard({ label, word, color, delay = 0, flipped }) {
  const dir = isHebrew(word) ? "rtl" : "ltr";
  return (
    <div className="flip-card">
      <div className={`flip-card__inner${flipped ? " flipped" : ""}`} style={{ transitionDelay: `${delay}ms` }}>
        <div className="flip-card__front">
          <span className="flip-card__question">?</span>
        </div>
        <div className={`flip-card__back flip-card__back--${color}`} dir={dir}>
          <span className="flip-card__label">{label}</span>
          <span className="flip-card__word">{word}</span>
        </div>
      </div>
    </div>
  );
}

export default function RevealCard({ playerGuess, computerGuess, visible }) {
  const [flipped, setFlipped] = useState(false);

  useEffect(() => {
    if (visible) {
      const t = setTimeout(() => setFlipped(true), 100);
      return () => clearTimeout(t);
    } else {
      setFlipped(false);
    }
  }, [visible]);

  if (!visible) return null;

  return (
    <div className="reveal-card">
      <FlipCard label="אתה" word={playerGuess} color="indigo" delay={0} flipped={flipped} />
      <FlipCard label="מחשב" word={computerGuess} color="teal" delay={150} flipped={flipped} />
    </div>
  );
}
