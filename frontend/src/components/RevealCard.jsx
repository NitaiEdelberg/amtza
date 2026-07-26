import { useEffect, useState } from "react";

function isHebrew(text) {
  return /[֐-׿]/.test(text ?? "");
}

function proximityColor(pct) {
  if (pct >= 80) return "#68d391";
  if (pct >= 55) return "#f6ad55";
  return "#fc8181";
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

export default function RevealCard({ playerGuess, computerGuess, proximity, lang, visible }) {
  const [flipped, setFlipped] = useState(false);
  const [showProximity, setShowProximity] = useState(false);
  const [barWidth, setBarWidth] = useState(0);

  useEffect(() => {
    if (visible) {
      const t1 = setTimeout(() => setFlipped(true), 100);
      const t2 = setTimeout(() => setShowProximity(true), 900);
      const t3 = setTimeout(() => setBarWidth(Math.max(4, Math.round((proximity ?? 0) * 100))), 1000);
      return () => { clearTimeout(t1); clearTimeout(t2); clearTimeout(t3); };
    } else {
      setFlipped(false);
      setShowProximity(false);
      setBarWidth(0);
    }
  }, [visible, proximity]);

  if (!visible) return null;

  const pct = Math.round((proximity ?? 0) * 100);
  const color = proximityColor(pct);
  const isHe = lang === "he";

  return (
    <div className="reveal-card">
      <div className="reveal-card__row">
        <FlipCard label={isHe ? "אתה" : "You"} word={playerGuess} color="indigo" delay={0} flipped={flipped} />
        <FlipCard label={isHe ? "מחשב" : "Computer"} word={computerGuess} color="teal" delay={150} flipped={flipped} />
      </div>

      {showProximity && (
        <div className="proximity-bar">
          <div className="proximity-bar__header">
            <span className="proximity-bar__label">
              {isHe ? "קרבה בין הניחושים:" : "Guess proximity:"}
            </span>
            <span className="proximity-bar__score" style={{ color }}>{pct}%</span>
          </div>
          <div className="proximity-bar__track">
            <div
              className="proximity-bar__fill"
              style={{ width: `${barWidth}%`, backgroundColor: color }}
            />
          </div>
        </div>
      )}
    </div>
  );
}
