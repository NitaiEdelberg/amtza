#!/bin/bash
# Download fastText word vectors for local development.
# Railway downloads them automatically on first deploy.

set -e

CACHE_DIR="${MODEL_CACHE_DIR:-$HOME/.amtza/models}"
mkdir -p "$CACHE_DIR"

echo "📥 Downloading Hebrew wiki vectors (~1.2GB)..."
wget -c -q --show-progress \
  -O "$CACHE_DIR/he.vec" \
  "https://dl.fbaipublicfiles.com/fasttext/vectors-wiki/wiki.he.vec"

echo "📥 Downloading English crawl vectors (~1.3GB compressed)..."
wget -c -q --show-progress \
  -O "$CACHE_DIR/en.vec.gz" \
  "https://dl.fbaipublicfiles.com/fasttext/vectors-crawl/cc.en.300.vec.gz"

echo ""
echo "✅ Done. Start the backend once to parse and cache as .npy files (~2 min):"
echo "   cd backend && uvicorn main:app --reload"
echo "   (MODEL_CACHE_DIR defaults to ~/.amtza/models — no env var needed locally)"
