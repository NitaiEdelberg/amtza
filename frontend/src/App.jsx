import { useState, useEffect, useRef } from "react";
import { checkHealth, getRandomPair, submitGuess, getHint, waitForLanguage, friendlyError, newGameId } from "./api";
import GameBoard from "./components/GameBoard";
import HowItWorks from "./components/HowItWorks";
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
  const [gameId, setGameId] = useState(null);
  const [waking, setWaking] = useState(null); // {seconds, unreachable} while waiting on the server
  // A ref, not state: nothing renders from it — it only decides whether pressing
  // Play can go straight through — so re-rendering the app on each poll is waste.
  const readyLangsRef = useRef([]);
  // Starting pairs from this visit's recent games. A play-tester got the same
  // pair twice in a row; with ~100 pairs per language that happens to someone.
  const recentPairsRef = useRef([]);

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
            ? "השרת לא מגיב, כנראה נרדם. נסו שוב בעוד רגע."
            : "The server isn't responding. It may be asleep. Try again in a moment."
        );
        setIsLoading(false);
        return;
      }
      readyLangsRef.current = [...readyLangsRef.current, lang];
    }

    try {
      let pair = await getRandomPair(lang);
      const key = (p) => `${p.word1}|${p.word2}`;
      for (let i = 0; i < 3 && recentPairsRef.current.includes(key(pair)); i++) {
        pair = await getRandomPair(lang);
      }
      recentPairsRef.current = [key(pair), ...recentPairsRef.current].slice(0, 8);
      setCurrentPair(pair);
      setGameId(newGameId());
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
        usedWords,
        gameId
      );
      // The response doesn't echo the pair, and the path history and the share
      // text both need it: without this every round's pair rendered empty and a
      // shared result read "Started from: undefined + undefined".
      setLastRound({ ...result, word1: currentPair.word1, word2: currentPair.word2 });
      setGamePhase("revealing");
    } catch (err) {
      // Shown inline next to the input (with any alternative spellings the
      // backend knows) rather than in a browser alert() the player must dismiss.
      setGuessError({
        message: friendlyError(err, currentPair.language === "he"),
        suggestions: err.suggestions || [],
      });
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
      const res = await getHint(currentPair.word1, currentPair.word2, usedWords);
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
        {/* The logo is Hebrew in both modes; a reader who doesn't read Hebrew
            should still be able to say the game's name. */}
        {!isHe && <p className="app-title__latin">Amtza</p>}
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
                  <p dir="rtl">אתם והמחשב מנסים למצוא את המילה שבאמצע, ביחד!</p>
                </>
              ) : (
                <>
                  <h2 dir="ltr">Welcome! 👋</h2>
                  <p dir="ltr">You and the computer try to find the word in the middle, together!</p>
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
                  : (selectedLang === "he" ? "בואו נשחק! 🎮" : "Let's play! 🎮")}
              </button>
              {waking && (
                <p className="idle-screen__waking" role="status">
                  {waking.unreachable
                    ? (selectedLang === "he"
                        ? "אין תשובה מהשרת. עוד מנסים…"
                        : "No answer yet. Still trying…")
                    : (selectedLang === "he"
                        ? "הכניסה הראשונה ביום יכולה לקחת עד דקה, כי השרת נרדם כשאף אחד לא משחק."
                        : "The first game of the day can take up to a minute, because the server naps when nobody is playing.")}
                </p>
              )}
              {startError && (
                <p className="idle-screen__error" role="alert">{startError}</p>
              )}
              {/* Play sits above the demo and the rules: on a phone the demo alone
                  used to fill the first screen and push Play out of sight. */}
              <HowItWorks lang={selectedLang} />
              {selectedLang === "he" ? (
                <>
                  <ul className="idle-screen__rules" dir="rtl">
                    <li>🧠 חשבו על מילה שבאמצע בין שתי המילים</li>
                    <li>🤫 אתם והמחשב עונים בו־זמנית, בלי לראות את התשובה של השני!</li>
                    <li>🔄 לא נפגשתם? שתי המילים שלכם הופכות לזוג החדש</li>
                    <li>🚫 אי אפשר לחזור על מילה שכבר נאמרה</li>
                    <li>🏆 מנצחים כששניכם מגיעים לאותה מילה</li>
                  </ul>
                </>
              ) : (
                <>
                  <ul className="idle-screen__rules" dir="ltr">
                    <li>🧠 Think of a word that sits between the two words</li>
                    <li>🤫 You and the computer answer at the same time. No peeking!</li>
                    <li>🔄 No match? Both of your words become the new pair</li>
                    <li>🚫 A word that's already been said can't be used again</li>
                    <li>🏆 You win when you both land on the same word</li>
                  </ul>
                </>
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
            usedWords={usedWords}
          />
        )}

        {gamePhase === "won" && lastRound && (
          <WinScreen
            winMessage={lastRound.win_message}
            rounds={roundNum}
            playerWord={lastRound.player_guess}
            computerWord={lastRound.computer_guess}
            // handleNextRound has already appended the winning round; adding it
            // again here showed it twice and made a round-2 win share as round 3.
            history={history}
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
