/** The page's only substantial text, and the reason a search engine has anything
 *  to index.
 *
 *  A game board is almost entirely words the app generated at runtime — a pair of
 *  nouns and a score — so a crawler landing here previously found a title, a
 *  subtitle and nothing else to tell it what the site is. This says it plainly,
 *  in prose, where both a reader and a crawler can see it.
 *
 *  It is real content, not a keyword block: it explains the game, the rules and
 *  how the computer chooses, which is what someone searching "משחק מילים אמצע"
 *  or "semantic word game" actually wants to read.
 */
export default function SiteFooter({ language = "he" }) {
  const isHe = language === "he";

  return (
    <footer className="site-footer" dir={isHe ? "rtl" : "ltr"}>
      {isHe ? (
        <>
          <section>
            <h2>מה זה אמצע?</h2>
            <p>
              אמצע הוא משחק מילים שיתופי בעברית ובאנגלית. המשחק מציג שתי מילים —
              נניח <strong>שמש</strong> ו<strong>ירח</strong> — ואתם כותבים את המילה
              שלדעתכם נמצאת בדיוק באמצע ביניהן מבחינת המשמעות. במקביל, גם המחשב
              בוחר מילה, בלי שאף אחד רואה את הבחירה של השני.
            </p>
            <p>
              שתי המילים נחשפות יחד והופכות לזוג המילים הבא. ככה ממשיכים, סיבוב אחרי
              סיבוב, עד שאתם והמחשב מגיעים לאותה מילה. זה לא משחק נגד המחשב אלא איתו:
              המטרה היא להיפגש באמצע.
            </p>
          </section>

          <section>
            <h2>איך משחקים</h2>
            <ol>
              <li>מקבלים זוג מילים פותח.</li>
              <li>כותבים מילה אחת שנמצאת לדעתכם באמצע.</li>
              <li>הבחירה שלכם והבחירה של המחשב נחשפות יחד.</li>
              <li>שתי המילים האלה הן הזוג של הסיבוב הבא.</li>
              <li>מנצחים כששניכם מגיעים לאותה מילה.</li>
            </ol>
            <p>
              רוב המשחקים נגמרים תוך ארבעה עד שישה סיבובים. אם נתקעתם, יש כפתור רמז
              שמציע כמה כיוונים — בלי לגלות את התשובה של המחשב.
            </p>
          </section>

          <section>
            <h2>איך המחשב בוחר מילה</h2>
            <p>
              לכל מילה יש ייצוג מספרי שנלמד מתוך ויקיפדיה העברית, כך שמילים בעלות
              משמעות דומה יושבות קרוב זו לזו. המחשב מחשב את הנקודה שבאמצע בין שתי
              המילים ומחפש סביבה את המילה המאוזנת ביותר — כזו שקשורה לשתי המילים
              במידה דומה, ולא מילה שנצמדת רק לאחת מהן. הוא בוחר רק מתוך רשימה של
              מילים יומיומיות, כדי שהתשובה תמיד תהיה מילה שמכירים.
            </p>
          </section>

          <p className="site-footer__meta">
            משחק חינמי, בלי הרשמה. עובד בדפדפן, גם בנייד.
          </p>
        </>
      ) : (
        <>
          <section>
            <h2>What is Amtza?</h2>
            <p>
              Amtza — Hebrew for "middle" — is a cooperative word game in Hebrew and
              English. You are shown two words, say <strong>sun</strong> and{" "}
              <strong>moon</strong>, and you type the word you think sits exactly
              between them in meaning. The computer picks its own middle word at the
              same moment, and neither of you can see the other's choice.
            </p>
            <p>
              Both words are revealed together and become the next pair. You keep
              going, round after round, until you and the computer land on the same
              word. It isn't a game against the computer but with it: the goal is to
              meet in the middle.
            </p>
          </section>

          <section>
            <h2>How to play</h2>
            <ol>
              <li>You are given a starting pair of words.</li>
              <li>Type the single word you think sits between them.</li>
              <li>Your choice and the computer's are revealed together.</li>
              <li>Those two words become the next round's pair.</li>
              <li>You win when you both land on the same word.</li>
            </ol>
            <p>
              Most games finish in four to six rounds. If you get stuck, the hint
              button offers a few directions — without giving away the computer's
              answer.
            </p>
          </section>

          <section>
            <h2>How the computer chooses</h2>
            <p>
              Every word has a numeric representation learned from a large body of
              text, so words with similar meanings sit near each other. The computer
              finds the point halfway between the two words and looks for the most
              balanced word around it — one related to both words roughly equally,
              rather than one glued to a single side. It only ever answers from a
              curated list of everyday words, so the answer is always something you
              would recognise.
            </p>
          </section>

          <p className="site-footer__meta">
            Free to play, no sign-up. Works in any browser, including on a phone.
          </p>
        </>
      )}
    </footer>
  );
}
