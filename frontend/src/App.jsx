import { useState, useEffect } from "react";
import { checkHealth, getRandomPair, submitGuess, getHint } from "./api";
import GameBoard from "./components/GameBoard";
import WinScreen from "./components/WinScreen";
import "./App.css";

// phases: loading → idle → guessing → revealing → won → idle
export default function App() {
  const [gamePhase, setGamePhase] = useState("loading");
  const [currentPair, setCurrentPair] = useState(null);
  const [lastRound, setLastRound] = useState(null);
  const [history, setHistory] = useState([]);
  const [roundNum, setRoundNum] = useState(1);
  const [isLoading, setIsLoading] = useState(false);
  const [hintWords, setHintWords] = useState([]);
  const [hintUsed, setHintUsed] = useState(false);
  const [selectedLang, setSelectedLang] = useState("he");

  // Poll /health until models are loaded
  useEffect(() => {
    let cancelled = false;
    async function poll() {
      try {
        const health = await checkHealth();
        if (cancelled) return;
        if (health.models_loaded) {
          setGamePhase("idle");
        } else {
          setTimeout(poll, 2500);
        }
      } catch {
        if (!cancelled) setTimeout(poll, 3000);
      }
    }
    poll();
    return () => { cancelled = true; };
  }, []);

  async function startGame(lang) {
    setIsLoading(true);
    try {
      const pair = await getRandomPair(lang);
      setCurrentPair(pair);
      setHistory([]);
      setRoundNum(1);
      setLastRound(null);
      setHintWords([]);
      setHintUsed(false);
      setGamePhase("guessing");
    } finally {
      setIsLoading(false);
    }
  }

  async function handleGuess(playerGuess) {
    setIsLoading(true);
    try {
      const result = await submitGuess(
        currentPair.word1,
        currentPair.word2,
        playerGuess,
        roundNum
      );
      setLastRound(result);
      setGamePhase("revealing");
    } catch (err) {
      alert(err.message);
    } finally {
      setIsLoading(false);
    }
  }

  function handleNextRound() {
    if (!lastRound) return;
    const newHistory = [...history, lastRound];
    setHistory(newHistory);

    if (lastRound.is_won) {
      setGamePhase("won");
      return;
    }

    setCurrentPair({
      word1: lastRound.new_pair[0],
      word2: lastRound.new_pair[1],
      language: lastRound.language,
    });
    setRoundNum((n) => n + 1);
    setHintWords([]);
    setHintUsed(false);
    setGamePhase("guessing");
  }

  async function handleGetHint() {
    if (hintUsed || !currentPair) return;
    try {
      const res = await getHint(currentPair.word1, currentPair.word2);
      setHintWords(res.hints || []);
      setHintUsed(true);
    } catch {
      // fail silently
    }
  }

  function handleNewGame() {
    setGamePhase("idle");
    setHistory([]);
    setLastRound(null);
  }

  const isHe = (currentPair?.language ?? selectedLang) === "he";

  return (
    <div className="app" dir={isHe ? "rtl" : "ltr"}>
      <header className="app-header">
        <h1 className="app-title">אמצע</h1>
        <p className="app-subtitle">
          {isHe ? "מצאו את המילה שבאמצע" : "Find the word in the middle"}
        </p>
      </header>

      <main className="app-main">
        {gamePhase === "loading" && (
          <div className="loading-screen">
            <div className="loading-screen__spinner">⟳</div>
            <p className="loading-screen__text">טוען מודלי שפה... ☕</p>
            <p className="loading-screen__sub">זה לוקח כדקה בפעם הראשונה</p>
          </div>
        )}

        {gamePhase === "idle" && (
          <div className="idle-screen">
            <div className="idle-screen__card">
              <h2 dir="rtl">ברוכים הבאים! 👋</h2>
              <p dir="rtl">אתה והמחשב מנסים למצוא את המילה שבאמצע — ביחד!</p>
              <ul className="idle-screen__rules" dir="rtl">
                <li>🧠 חשבו על מילה שבאמצע בין שתי המילים</li>
                <li>🤫 אתם שולחים בו זמנית — לא רואים אחד את השני!</li>
                <li>🔄 הניחוש שלכם הופך לזוג החדש</li>
                <li>🏆 ניצחתם כשמגיעים לאותה מילה</li>
              </ul>
              <div className="idle-screen__lang-select">
                <button
                  className={`btn btn--lang${selectedLang === "he" ? " active" : ""}`}
                  onClick={() => setSelectedLang("he")}
                >🇮🇱 עברית</button>
                <button
                  className={`btn btn--lang${selectedLang === "en" ? " active" : ""}`}
                  onClick={() => setSelectedLang("en")}
                >🇺🇸 English</button>
              </div>
              <button
                className="btn btn--primary btn--large"
                onClick={() => startGame(selectedLang)}
                disabled={isLoading}
              >
                {selectedLang === "he" ? "בואו נשחק! 🎮" : "Let's Play! 🎮"}
              </button>
            </div>
          </div>
        )}

        {(gamePhase === "guessing" || gamePhase === "revealing") && currentPair && (
          <GameBoard
            gamePhase={gamePhase}
            currentPair={currentPair}
            lastRound={lastRound}
            history={history}
            roundNum={roundNum}
            onGuess={handleGuess}
            onNextRound={handleNextRound}
            isLoading={isLoading}
            onGetHint={handleGetHint}
            hintWords={hintWords}
            hintUsed={hintUsed}
          />
        )}

        {gamePhase === "won" && lastRound && (
          <WinScreen
            winMessage={lastRound.win_message}
            rounds={roundNum}
            lastWord={lastRound.player_guess}
            history={[...history, lastRound]}
            onNewGame={handleNewGame}
            language={lastRound.language}
          />
        )}
      </main>
    </div>
  );
}
