import Confetti from "react-confetti";
import { useEffect, useState } from "react";
import PathHistory from "./PathHistory";

export default function WinScreen({ winMessage, rounds, playerWord, computerWord, history, onNewGame, language }) {
  const [size, setSize] = useState({ width: window.innerWidth, height: window.innerHeight });
  const sameWord = playerWord?.toLowerCase() === computerWord?.toLowerCase();

  useEffect(() => {
    const onResize = () => setSize({ width: window.innerWidth, height: window.innerHeight });
    window.addEventListener("resize", onResize);
    return () => window.removeEventListener("resize", onResize);
  }, []);

  const isHe = language === "he";

  return (
    <div className="win-screen">
      <Confetti
        width={size.width}
        height={size.height}
        recycle={false}
        numberOfPieces={350}
        gravity={0.2}
      />
      <div className="win-screen__content">
        <div className="win-screen__emoji">🎉</div>
        <h2 className="win-screen__title">{winMessage}</h2>
        {sameWord ? (
          <p className="win-screen__word">{playerWord}</p>
        ) : (
          <p className="win-screen__word win-screen__word--pair">
            <span>{playerWord}</span>
            <span className="win-screen__word-sep">≈</span>
            <span>{computerWord}</span>
          </p>
        )}
        <p className="win-screen__stat">
          {isHe ? `הגענו באמצע בסיבוב ${rounds}!` : `Converged in ${rounds} round${rounds === 1 ? "" : "s"}!`}
        </p>
        <PathHistory history={history} language={language} />
        <button className="btn btn--primary btn--large" onClick={onNewGame}>
          {isHe ? "משחק חדש 🎮" : "New Game 🎮"}
        </button>
      </div>
    </div>
  );
}
