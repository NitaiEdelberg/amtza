import { useState } from "react";
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
}) {
  const isRevealing = gamePhase === "revealing";
  const isHe = currentPair?.language === "he";

  return (
    <div className="game-board">
      <WordPair
        word1={currentPair.word1}
        word2={currentPair.word2}
        roundNum={roundNum}
      />

      {gamePhase === "guessing" && (
        <>
          <GuessInput
            onSubmit={onGuess}
            disabled={isRevealing}
            currentPair={currentPair}
            isLoading={isLoading}
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
          <button className="btn btn--primary" onClick={onNextRound}>
            {isHe ? "סיבוב הבא ←" : "Next Round →"}
          </button>
        </>
      )}

      {history.length > 0 && gamePhase === "guessing" && (
        <PathHistory history={history} />
      )}
    </div>
  );
}
