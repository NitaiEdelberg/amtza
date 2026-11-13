import { useState } from "react";
import { shareText } from "../share";

export default function ShareButton({ history, language }) {
  const [status, setStatus] = useState(null); // "copied" | "failed"
  const isHe = language === "he";
  if (!history?.length) return null;

  async function share() {
    const text = shareText(history, language, window.location.origin);
    try {
      // The native sheet on phones is where LinkedIn and WhatsApp live.
      if (navigator.share) {
        await navigator.share({ text });
        return;
      }
      await navigator.clipboard.writeText(text);
      setStatus("copied");
    } catch (e) {
      // Closing the share sheet rejects with AbortError: not a failure.
      if (e?.name !== "AbortError") setStatus("failed");
    }
  }

  return (
    <div className="share">
      <button className="btn btn--secondary" onClick={share}>
        {isHe ? "שתפו את התוצאה 📤" : "Share your result 📤"}
      </button>
      {status === "copied" && (
        <p className="share__status" role="status">{isHe ? "הועתק! אפשר להדביק 📋" : "Copied! Paste it anywhere 📋"}</p>
      )}
      {status === "failed" && (
        <p className="share__status" role="status">{isHe ? "לא הצלחנו להעתיק" : "Couldn't copy that"}</p>
      )}
    </div>
  );
}
