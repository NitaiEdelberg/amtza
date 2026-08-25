#!/usr/bin/env bash
# Publish the prebuilt embedding caches as a GitHub Release, so the deployed
# backend can download them instead of rebuilding from raw fastText vectors.
#
# The problem this solves: a free container has no persistent disk. Without this,
# every cold start re-streams ~670MB of raw fastText vectors and parses them —
# minutes, repeated, for a result that never changes. The finished artifacts are
# ~180MB and load in seconds.
#
# Run this once locally (you already have the caches), then set PREBUILT_CACHE_URL
# on the backend host to the printed URL.
#
# Usage:  ./scripts/publish_model_cache.sh [tag]
set -euo pipefail

TAG="${1:-models-v1}"
CACHE_DIR="${MODEL_CACHE_DIR:-$HOME/.amtza/models}"
# The good-word masks are no longer published: the playable pool is built from
# backend/data/{lang}_playable.txt at load, which is a set lookup rather than the
# filter pass that used to be worth caching.
FILES=(he_v4.npy he_v4_words.pkl en_v4.npy en_v4_words.pkl)

command -v gh >/dev/null || { echo "error: the GitHub CLI (gh) is required"; exit 1; }

echo "Cache directory: $CACHE_DIR"
missing=0
for f in "${FILES[@]}"; do
  if [[ -f "$CACHE_DIR/$f" ]]; then
    printf '  %-22s %s\n' "$f" "$(du -h "$CACHE_DIR/$f" | cut -f1)"
  else
    echo "  MISSING: $f"; missing=1
  fi
done
if (( missing )); then
  echo
  echo "Run the backend once locally to build the caches, then re-run this script:"
  echo "  cd backend && ./venv/bin/uvicorn main:app --port 8000"
  exit 1
fi

# The matrices must be float16 — the whole point is that they fit in 512MB.
python3 - "$CACHE_DIR" <<'PY'
import sys, numpy as np, pathlib
cache = pathlib.Path(sys.argv[1])
for lang in ("he", "en"):
    m = np.load(cache / f"{lang}_v4.npy", mmap_mode="r")
    assert m.dtype == np.float16, f"{lang}_v4.npy is {m.dtype}, expected float16"
    print(f"  {lang}: {m.shape[0]:,} x {m.shape[1]} {m.dtype} OK")
PY

echo
echo "Publishing release '$TAG'..."
if gh release view "$TAG" >/dev/null 2>&1; then
  gh release upload "$TAG" "${FILES[@]/#/$CACHE_DIR/}" --clobber
else
  gh release create "$TAG" "${FILES[@]/#/$CACHE_DIR/}" \
    --title "Prebuilt embedding caches" \
    --notes "float16 fastText matrices, vocabularies for the amtza backend. Point PREBUILT_CACHE_URL at this release to skip rebuilding them on every cold start."
fi

REPO="$(gh repo view --json nameWithOwner -q .nameWithOwner)"
echo
echo "Done. Set this on the backend host:"
echo "  PREBUILT_CACHE_URL=https://github.com/$REPO/releases/download/$TAG"
