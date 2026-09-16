import { useState } from "react";

/** "Why that word?" — the actual arithmetic behind the computer's pick.
 *
 * No language model is involved, and that is the point: the choice genuinely IS
 * these two numbers, so showing them is the whole truth rather than a plausible
 * story told about it afterwards. The computer scored every playable word by its
 * weaker link to the two words on screen and kept the best one.
 *
 * Collapsed by default. It's an answer to a question a curious player asks once,
 * not something to put in front of everyone mid-round.
 */
export default function WhyPanel({ word1, word2, computerGuess, reason, lang }) {
  const [open, setOpen] = useState(false);
  if (!reason) return null;

  const isHe = lang === "he";
  const pct = (x) => Math.round((x ?? 0) * 100);
  const s1 = pct(reason.similarity_to_word1);
  const s2 = pct(reason.similarity_to_word2);
  const considered = reason.considered;

  return (
    <div className="why" dir={isHe ? "rtl" : "ltr"}>
      <button
        className="btn btn--ghost why__toggle"
        onClick={() => setOpen((o) => !o)}
        aria-expanded={open}
      >
        {isHe ? "🤖 למה המילה הזאת?" : "🤖 Why that word?"}
      </button>

      {open && (
        <div className="why__body" role="region">
          {isHe ? (
            <>
              <p>
                לכל מילה יש ייצוג מספרי, ומילים בעלות משמעות דומה יושבות קרוב זו לזו.
                בדקתי את כל <strong>{considered?.toLocaleString("he-IL")}</strong> המילים
                שמותר לי לענות בהן, וחיפשתי את זו שהקשר החלש שלה לשתי המילים הוא החזק ביותר.
              </p>
              <ul className="why__scores">
                <li><span>{computerGuess}</span> ↔ <span>{word1}</span><b>{s1}%</b></li>
                <li><span>{computerGuess}</span> ↔ <span>{word2}</span><b>{s2}%</b></li>
              </ul>
              <p className="why__note">
                לא בחרתי את המילה הקרובה ביותר לאחת מהן, אלא את המאוזנת ביותר בין שתיהן.
              </p>
            </>
          ) : (
            <>
              <p>
                Every word has a numeric representation, and words with similar meanings
                sit near each other. I checked all{" "}
                <strong>{considered?.toLocaleString("en-US")}</strong> words I'm allowed to
                answer with, looking for the one whose <em>weaker</em> link to the two
                words was strongest.
              </p>
              <ul className="why__scores">
                <li><span>{computerGuess}</span> ↔ <span>{word1}</span><b>{s1}%</b></li>
                <li><span>{computerGuess}</span> ↔ <span>{word2}</span><b>{s2}%</b></li>
              </ul>
              <p className="why__note">
                Not the word closest to either one — the most balanced between both.
              </p>
            </>
          )}
        </div>
      )}
    </div>
  );
}
