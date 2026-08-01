import { useEffect } from "react";
import WordPair from "./WordPair";
import GuessInput from "./GuessInput";
import RevealCard from "./RevealCard";
import SimilarityMeter from "./SimilarityMeter";
import PathHistory from "./PathHistory";

export default function GameBoard({
  gamePhase,
  currentPair,
  lastRound,
  history,
  roundNum,
  onGuess,
  onNextRound,
  isLoading,
  onGetHint,
  hintWords,
  hintUsed,
  guessError,
  onClearGuessError,
}) {
  const isRevealing = gamePhase === "revealing";
  const isHe = currentPair?.language === "he";

  // Auto-advance to win screen after reveal animation completes
  useEffect(() => {
    if (isRevealing && lastRound?.is_won) {
      const t = setTimeout(() => onNextRound(), 2200);
      return () => clearTimeout(t);
    }
  }, [isRevealing, lastRound?.is_won]);

  return (
    <div className="game-board">
      <WordPair
        word1={currentPair.word1}
        word2={currentPair.word2}
        roundNum={roundNum}
        language={currentPair?.language}
      />

      {gamePhase === "guessing" && (
        <>
          <GuessInput
            key={`${currentPair.word1}|${currentPair.word2}`}
            onSubmit={onGuess}
            disabled={isRevealing}
            currentPair={currentPair}
            isLoading={isLoading}
            error={guessError}
            onClearError={onClearGuessError}
          />
          <div className="game-board__hint-row">
            <button
              className="btn btn--ghost"
              onClick={onGetHint}
              disabled={hintUsed || isLoading}
            >
              {hintUsed
                ? (isHe ? "רמז נוצל" : "Hint used")
                : (isHe ? "💡 רמז" : "💡 Hint")}
            </button>
            {hintWords.length > 0 && (
              <span className="hint-words" dir={isHe ? "rtl" : "ltr"}>
                {isHe ? "כיוון: " : "Direction: "}
                {hintWords.join(" · ")}
              </span>
            )}
          </div>
        </>
      )}

      {isRevealing && lastRound && (
        <>
          <RevealCard
            playerGuess={lastRound.player_guess}
            computerGuess={lastRound.computer_guess}
            proximity={lastRound.player_computer_similarity}
            lang={lastRound.language}
            visible={true}
          />
          <SimilarityMeter
            similarity={lastRound.player_similarity}
            lang={lastRound.language}
            visible={true}
          />
          {lastRound.funny_message && (
            <p className="funny-message">{lastRound.funny_message}</p>
          )}
          {!lastRound.is_won && (
            <button className="btn btn--primary" onClick={onNextRound}>
              {isHe ? "סיבוב הבא ←" : "Next Round →"}
            </button>
          )}
        </>
      )}

      {history.length > 0 && gamePhase === "guessing" && (
        <PathHistory history={history} language={currentPair?.language} />
      )}
    </div>
  );
}
