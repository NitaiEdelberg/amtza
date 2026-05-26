function isHebrew(text) {
  return /[֐-׿]/.test(text);
}

function WordChip({ word, color }) {
  const dir = isHebrew(word) ? "rtl" : "ltr";
  return (
    <div className={`word-chip word-chip--${color}`} dir={dir}>
      {word}
    </div>
  );
}

export default function WordPair({ word1, word2, roundNum }) {
  return (
    <div className="word-pair">
      <div className="word-pair__round">סיבוב {roundNum}</div>
      <div className="word-pair__words">
        <WordChip word={word1} color="blue" />
        <span className="word-pair__vs">↔</span>
        <WordChip word={word2} color="purple" />
      </div>
      <p className="word-pair__hint">מה באמצע?</p>
    </div>
  );
}
