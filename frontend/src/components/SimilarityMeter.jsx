import { useEffect, useState } from "react";

function getColor(pct) {
  if (pct < 30) return "#fc8181";
  if (pct < 60) return "#f6ad55";
  return "#68d391";
}

function getLabel(pct, lang) {
  if (lang === "he") {
    if (pct < 30) return "רחוק מהאמצע";
    if (pct < 60) return "בכיוון הנכון";
    if (pct < 80) return "קרוב לאמצע!";
    return "כמעט מושלם! 🌟";
  } else {
    if (pct < 30) return "Far from center";
    if (pct < 60) return "Right direction";
    if (pct < 80) return "Close to middle!";
    return "Almost perfect! 🌟";
  }
}

export default function SimilarityMeter({ similarity, lang, visible }) {
  const [width, setWidth] = useState(0);

  useEffect(() => {
    if (visible) {
      const t = setTimeout(() => setWidth(Math.max(5, Math.round(similarity * 100))), 700);
      return () => clearTimeout(t);
    } else {
      setWidth(0);
    }
  }, [visible, similarity]);

  if (!visible) return null;

  const pct = Math.round(similarity * 100);
  const label = getLabel(pct, lang);

  return (
    <div className="similarity-meter">
      <div className="similarity-meter__header">
        <span>{lang === "he" ? "הניחוש שלך:" : "Your guess:"}</span>
        <span className="similarity-meter__score">{pct}%</span>
        <span>{label}</span>
      </div>
      <div className="similarity-meter__track">
        <div
          className="similarity-meter__fill"
          style={{ width: `${width}%`, backgroundColor: getColor(pct) }}
        />
      </div>
    </div>
  );
}
