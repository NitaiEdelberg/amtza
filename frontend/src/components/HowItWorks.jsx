import { useEffect, useState } from "react";

/** A ten-second silent demo of one round, on the welcome screen.
 *
 * The rules list explains the game correctly and still leaves people unsure what
 * actually happens, because the mechanic — your word and the computer's become
 * the next pair — is a *motion*, and a bulleted list can't show motion. This
 * plays it once, slowly enough to follow.
 *
 * Deliberately not a blocking tutorial: it sits above the Play button and loops,
 * so anyone who already knows the game just presses Play and never reads it.
 * Anyone who prefers reading still has the rules underneath.
 */
// How long each step stays on screen before the next appears. Index 0 is the
// short beat before anything shows; the last entry is the pause on the punchline
// before the demo starts over.
const STEP_MS = [700, 1200, 1200, 1500, 1200, 1600, 2600];

export default function HowItWorks({ lang }) {
  const isHe = lang === "he";
  const [step, setStep] = useState(0);

  // One timer at a time, each scheduling the next step and wrapping back to 0 at
  // the end, so the demo loops for anyone who glanced away mid-way. Advancing
  // inside the timeout rather than resetting state in the effect body keeps this
  // out of render: a synchronous setState here would run on every commit.
  useEffect(() => {
    const id = setTimeout(
      () => setStep((s) => (s + 1) % STEP_MS.length),
      STEP_MS[step]
    );
    return () => clearTimeout(id);
  }, [step]);

  const pair = isHe ? ["תפוח", "רופא"] : ["Apple", "Doctor"];
  const you = isHe ? "בית חולים" : "Hospital";
  const computer = isHe ? "תרופה" : "Medicine";

  return (
    <div className="howto" dir={isHe ? "rtl" : "ltr"} aria-label={isHe ? "איך זה עובד" : "How it works"}>
      <h3 className="howto__title">{isHe ? "איך זה עובד?" : "How does it work?"}</h3>

      <div className={`howto__row${step >= 1 ? " in" : ""}`}>
        <span className="howto__chip howto__chip--blue">{pair[0]}</span>
        <span className="howto__vs">↔</span>
        <span className="howto__chip howto__chip--purple">{pair[1]}</span>
      </div>

      <div className={`howto__line${step >= 2 ? " in" : ""}`}>
        <span className="howto__who">{isHe ? "אתם חושבים על:" : "You think of:"}</span>
        <strong>{you}</strong>
      </div>

      <div className={`howto__line${step >= 3 ? " in" : ""}`}>
        <span className="howto__who">{isHe ? "המחשב חושב על:" : "Computer thinks of:"}</span>
        <strong>{computer}</strong>
      </div>

      <div className={`howto__arrow${step >= 4 ? " in" : ""}`}>↓</div>

      <div className={`howto__row${step >= 5 ? " in" : ""}`}>
        <span className="howto__chip howto__chip--blue">{you}</span>
        <span className="howto__vs">↔</span>
        <span className="howto__chip howto__chip--purple">{computer}</span>
      </div>

      <p className={`howto__punch${step >= 6 ? " in" : ""}`}>
        {isHe ? "ממשיכים עד שנפגשים באמצע! 🎯" : "Keep going until you meet in the middle! 🎯"}
      </p>
    </div>
  );
}
