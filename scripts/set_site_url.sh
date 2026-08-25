#!/usr/bin/env bash
# Point the site at a different origin.
#
# The deployed URL is baked into the HTML rather than read from an env var,
# because the things that need it — canonical, hreflang, og:image, JSON-LD @id,
# robots.txt, sitemap.xml — are read by crawlers that never run the app, and
# several of them must be absolute. That means it appears in three files, which
# is three chances to update two of them. Hence this script.
#
# Usage:  ./scripts/set_site_url.sh https://yourdomain.com
#
# Run it, rebuild the frontend, and re-submit the sitemap in Search Console.
set -euo pipefail

NEW="${1:-}"
if [[ -z "$NEW" ]]; then
  echo "usage: $0 https://yourdomain.com" >&2
  exit 1
fi
# Trailing slashes would produce https://x.com//sitemap.xml and a canonical that
# disagrees with itself.
NEW="${NEW%/}"
if [[ ! "$NEW" =~ ^https://[a-zA-Z0-9.-]+$ ]]; then
  echo "error: expected a bare https origin, e.g. https://amtza.com (got '$NEW')" >&2
  exit 1
fi

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
FILES=(
  "$ROOT/frontend/index.html"
  "$ROOT/frontend/public/robots.txt"
  "$ROOT/frontend/public/sitemap.xml"
)

# Find whatever origin is in there now, so this works on the second move as well
# as the first.
OLD="$(grep -ohE 'https://[a-zA-Z0-9.-]+' "$ROOT/frontend/public/robots.txt" | head -1)"
if [[ -z "$OLD" ]]; then
  echo "error: could not determine the current site URL from robots.txt" >&2
  exit 1
fi
if [[ "$OLD" == "$NEW" ]]; then
  echo "Already set to $NEW — nothing to do."
  exit 0
fi

echo "  $OLD  ->  $NEW"
for f in "${FILES[@]}"; do
  count=$(grep -c "$OLD" "$f" || true)
  sed -i "s|${OLD}|${NEW}|g" "$f"
  printf '    %-34s %s replaced\n' "${f#$ROOT/}" "$count"
done

remaining=$(grep -rl "$OLD" "$ROOT/frontend" 2>/dev/null || true)
if [[ -n "$remaining" ]]; then
  echo
  echo "  NOTE: '$OLD' still appears in:"
  echo "$remaining" | sed 's/^/    /'
fi

cat <<EOF

Done. Next:
  1. cd frontend && npm run build          (Vite copies public/ verbatim)
  2. commit + push so Netlify redeploys
  3. Search Console: add the new property, submit ${NEW}/sitemap.xml
  4. Keep the old domain redirecting to the new one if it had any traffic
EOF
