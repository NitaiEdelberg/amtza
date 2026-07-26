function isHebrew(text) {
  return /[֐-׿]/.test(text ?? "");
}

function Word({ text }) {
  return (
    <span className="path-word" dir={isHebrew(text) ? "rtl" : "ltr"}>
      {text}
    </span>
  );
}

export default function PathHistory({ history, language }) {
  if (!history || history.length === 0) return null;
  const isHe = language === "he" || (history[0] && isHebrew(history[0].word1));

  return (
    <div className="path-history">
      <h3 className="path-history__title">
        {isHe ? "מסלול ההתכנסות" : "Convergence path"}
      </h3>
      <div className="path-history__list">
        {history.map((round, i) => (
          <div key={i} className="path-history__round">
            <div className="path-history__pair">
              <Word text={round.word1} />
              <span className="path-history__arrow">↔</span>
              <Word text={round.word2} />
            </div>
            <div className="path-history__guesses">
              <div className="path-history__guess path-history__guess--player">
                <span className="path-history__guess-label">{isHe ? "אתה" : "You"}</span>
                <Word text={round.player_guess} />
                <span className="path-history__pct">{Math.round(round.player_similarity * 100)}%</span>
              </div>
              <div className="path-history__guess path-history__guess--computer">
                <span className="path-history__guess-label">{isHe ? "מחשב" : "Computer"}</span>
                <Word text={round.computer_guess} />
              </div>
            </div>
            {i < history.length - 1 && <div className="path-history__connector">↓</div>}
          </div>
        ))}
      </div>
    </div>
  );
}
