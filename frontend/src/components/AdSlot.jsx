import { useEffect, useRef } from "react";

const CLIENT = import.meta.env.VITE_ADSENSE_CLIENT || "";
const SLOT = import.meta.env.VITE_ADSENSE_SLOT || "";

/** Load the AdSense library once, on the first slot that actually renders.
 *
 * Not in index.html: a script tag there runs on every visit, including the ones
 * that never reach round two, and it is a third-party request on the critical
 * path of a page whose whole problem is how long it takes to become playable. */
let scriptPromise = null;
function loadAdSense(client) {
  if (scriptPromise) return scriptPromise;
  scriptPromise = new Promise((resolve, reject) => {
    const s = document.createElement("script");
    s.async = true;
    s.crossOrigin = "anonymous";
    s.src =
      "https://pagead2.googlesyndication.com/pagead/js/adsbygoogle.js?client=" +
      encodeURIComponent(client);
    s.onload = resolve;
    // An ad blocker rejecting this is the common case, not an error worth surfacing.
    s.onerror = reject;
    document.head.appendChild(s);
  });
  return scriptPromise;
}

/** A single responsive ad unit.
 *
 * Renders nothing at all unless VITE_ADSENSE_CLIENT and VITE_ADSENSE_SLOT are
 * both set at build time, so the game ships ad-free until there is an approved
 * publisher account to point it at. (AdSense won't review a site that has no
 * content yet, so the ID genuinely arrives after the first deploy.)
 *
 * The wrapper keeps its height whether or not an ad fills, because the slot sits
 * inside a running game: a block that appears late and pushes the guess box down
 * both costs Cumulative Layout Shift, which Google ranks on, and moves the input
 * under a player's finger mid-tap.
 */
export default function AdSlot({ label }) {
  const pushed = useRef(false);

  useEffect(() => {
    if (!CLIENT || !SLOT || pushed.current) return;
    pushed.current = true; // React 18 StrictMode mounts twice; AdSense throws on a re-push.
    loadAdSense(CLIENT)
      .then(() => {
        (window.adsbygoogle = window.adsbygoogle || []).push({});
      })
      .catch(() => {
        /* blocked or offline — the reserved space simply stays empty */
      });
  }, []);

  if (!CLIENT || !SLOT) return null;

  return (
    <aside className="ad-slot" aria-label={label}>
      <span className="ad-slot__label">{label}</span>
      <ins
        className="adsbygoogle ad-slot__unit"
        style={{ display: "block" }}
        data-ad-client={CLIENT}
        data-ad-slot={SLOT}
        data-ad-format="horizontal"
        data-full-width-responsive="true"
      />
    </aside>
  );
}
