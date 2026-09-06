import { useState, useEffect, useRef } from "react";
import { checkHealth, getRandomPair, submitGuess, getHint, waitForLanguage } from "./api";
import GameBoard from "./components/GameBoard";
import SiteFooter from "./components/SiteFooter";
import WinScreen from "./components/WinScreen";
import "./App.css";

// phases: idle → guessing → revealing → won → idle
//
// There is deliberately no "loading" phase. A free-tier backend that has gone to
// sleep needs up to a minute to wake and load its vectors, and the app used to
// hold a spinner in front of the player for that entire time. Now the welcome
// screen renders immediately, the health poll wakes the server in the background
// while the player reads the rules, and the wait — if any of it is left by the
// time they press Play — happens on the button.
export default function App() {
  const [gamePhase, setGamePhase] = useState("idle");
  const [currentPair, setCurrentPair] = useState(null);
  const [lastRound, setLastRound] = useState(null);
  const [history, setHistory] = useState([]);
  const [roundNum, setRoundNum] = useState(1);
  const [isLoading, setIsLoading] = useState(false);
  const [hintWords, setHintWords] = useState([]);
  const [hintUsed, setHintUsed] = useState(false);
  const [selectedLang, setSelectedLang] = useState("he");
  const [usedWords, setUsedWords] = useState([]);
  const [guessError, setGuessError] = useState(null);
  const [startError, setStartError] = useState(null);
  const [waking, setWaking] = useState(null); // {seconds, unreachable} while waiting on the server
  // A ref, not state: nothing renders from it — it only decides whether pressing
  // Play can go straight through — so re-rendering the app on each poll is waste.
  const readyLangsRef = useRef([]);

  // Warm the backend the moment the page opens, and keep a note of which
  // languages are playable.
  //
  // The request itself is the point as much as the answer is: a sleeping free
  // instance wakes on any request, so this poll starts the clock while the player
  // is still reading the rules. Nothing here blocks rendering — the result only
  // decides whether pressing Play is instant or has to wait a few more seconds.
  useEffect(() => {
    let cancelled = false;

    async function poll() {
      try {
        const health = await checkHealth();
        if (cancelled) return;
        const langs = health.languages || (health.models_loaded ? ["he", "en"] : []);
        readyLangsRef.current = langs;
        if (langs.includes("he") && langs.includes("en")) return; // fully up; stop polling
      } catch {
        // Ignore: startGame surfaces an unreachable server, where it's actionable.
      }
      if (!cancelled) setTimeout(poll, 3000);
    }

    poll();
    return () => { cancelled = true; };
  }, []);

  async function startGame(lang) {
    setIsLoading(true);
    setStartError(null);

    // Only wait if this language isn't in yet — and wait here, on the button,
    // rather than behind a full-screen spinner the player met on arrival.
    if (!readyLangsRef.current.includes(lang)) {
      setWaking({ seconds: 0, unreachable: false });
      const ready = await waitForLanguage(lang, { onTick: setWaking });
      setWaking(null);
      if (!ready) {
        setStartError(
          lang === "he"
            ? "השרת לא מגיב. הוא כנראה נרדם. נסו שוב בעוד רגע."
            : "The server isn't responding. It may be asleep. Try again in a moment."
        );
        setIsLoading(false);
        return;
      }
      readyLangsRef.current = [...readyLangsRef.current, lang];
    }

    try {
      const pair = await getRandomPair(lang);
      setCurrentPair(pair);
      setHistory([]);
      setRoundNum(1);
      setLastRound(null);
      setHintWords([]);
      setHintUsed(false);
      setUsedWords([pair.word1, pair.word2]);
      setGuessError(null);
      setGamePhase("guessing");
    } catch {
      // Without this the button simply stopped spinning and nothing happened.
      setStartError(
        lang === "he"
          ? "לא הצלחנו להתחיל משחק. בדקו את החיבור ונסו שוב."
          : "Couldn't start a game. Check your connection and try again."
      );
    } finally {
      setIsLoading(false);
    }
  }

  async function handleGuess(playerGuess) {
    setIsLoading(true);
    setGuessError(null);
    try {
      const result = await submitGuess(
        currentPair.word1,
        currentPair.word2,
        playerGuess,
        roundNum,
        usedWords
      );
      setLastRound(result);
      setGamePhase("revealing");
    } catch (err) {
      // Shown inline next to the input (with any alternative spellings the
      // backend knows) rather than in a browser alert() the player must dismiss.
      setGuessError({ message: err.message, suggestions: err.suggestions || [] });
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
    setUsedWords((prev) => [...prev, lastRound.player_guess, lastRound.computer_guess]);
    setRoundNum((n) => n + 1);
    setHintWords([]);
    setHintUsed(false);
    setGuessError(null);
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
        {gamePhase === "idle" && (
          <div className="idle-screen">
            <div className="idle-screen__card">
              {selectedLang === "he" ? (
                <>
                  <h2 dir="rtl">ברוכים הבאים! 👋</h2>
                  <p dir="rtl">אתה והמחשב מנסים למצוא את המילה שבאמצע, ביחד!</p>
                  <ul className="idle-screen__rules" dir="rtl">
                    <li>🧠 חשבו על מילה שבאמצע בין שתי המילים</li>
                    <li>🤫 אתם שולחים בו זמנית, לא רואים אחד את השני!</li>
                    <li>🔄 הניחוש שלכם הופך לזוג החדש</li>
                    <li>🏆 ניצחתם כשמגיעים לאותה מילה</li>
                  </ul>
                </>
              ) : (
                <>
                  <h2 dir="ltr">Welcome! 👋</h2>
                  <p dir="ltr">You and the computer try to find the word in the middle, together!</p>
                  <ul className="idle-screen__rules" dir="ltr">
                    <li>🧠 Think of a word that sits between the two given words</li>
                    <li>🤫 You both submit at the same time, no peeking at each other's guess!</li>
                    <li>🔄 Your guess becomes the new pair</li>
                    <li>🏆 You win when you both land on the same word</li>
                  </ul>
                </>
              )}
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
                {waking
                  ? (selectedLang === "he" ? "מעירים את השרת… ⏳" : "Waking the server… ⏳")
                  : (selectedLang === "he" ? "בואו נשחק! 🎮" : "Let's Play! 🎮")}
              </button>
              {waking && (
                <p className="idle-screen__waking" role="status">
                  {waking.unreachable
                    ? (selectedLang === "he"
                        ? "אין תשובה מהשרת. עוד מנסים…"
                        : "No answer yet. Still trying…")
                    : (selectedLang === "he"
                        ? "הפעם הראשונה ביום לוקחת כדקה. השרת נרדם כשאף אחד לא משחק"
                        : "The first visit of the day takes about a minute. The server sleeps when nobody is playing")}
                </p>
              )}
              {startError && (
                <p className="idle-screen__error" role="alert">{startError}</p>
              )}
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
            guessError={guessError}
            onClearGuessError={() => setGuessError(null)}
            onNewGame={handleNewGame}
            hintWords={hintWords}
            hintUsed={hintUsed}
          />
        )}

        {gamePhase === "won" && lastRound && (
          <WinScreen
            winMessage={lastRound.win_message}
            rounds={roundNum}
            playerWord={lastRound.player_guess}
            computerWord={lastRound.computer_guess}
            history={[...history, lastRound]}
            onNewGame={handleNewGame}
            language={lastRound.language}
          />
        )}
      </main>

      {/* Only on the welcome screen. It's the page a search result lands on, and
          the one moment the player isn't mid-round — prose under a live game board
          would just be something to scroll past. */}
      {gamePhase === "idle" && <SiteFooter language={selectedLang} />}
    </div>
  );
}
