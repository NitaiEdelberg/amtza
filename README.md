---
title: Amtza
emoji: 🎯
colorFrom: yellow
colorTo: indigo
sdk: docker
app_port: 7860
pinned: false
---

# אמצע 🎯

**A cooperative semantic word game** — you and the computer both try to find the word that sits *in the middle* of two given words. Your guesses form the next pair. Keep going until you both land on the same word.

<!-- The YAML block above configures the Hugging Face Space that hosts the backend.
     GitHub renders it as a small table; Hugging Face requires it. -->


> *Inspired by the Israeli word game "אמצע" played between friends.*

---

## How to Play

1. Two words appear on screen (e.g., **חביתה** ↔ **בן גוריון**)
2. You type a word you think is semantically "in the middle"
3. The computer also picks the word closest to the semantic midpoint
4. Both answers are revealed simultaneously
5. Your word + the computer's word form the **new pair**
6. Repeat until you both guess the same word — **you win!**

The computer plays the semantic midpoint, filtered to real, everyday words (it won't
throw junk tokens, proper nouns, or grammatical fragments at you). The challenge is
thinking like the algorithm. If you circle the same territory for a while, a gentle
"homing" mechanism relaxes the match bar each round so every game converges.

---

## Tech Stack

| Layer | Tech |
|-------|------|
| Backend | Python FastAPI + fastText word embeddings (300d) |
| Embeddings | Facebook/Meta fastText — Hebrew (wiki) + English (Common Crawl) |
| Frontend | React 19 + Vite + framer-motion |
| Deployment | Railway (backend) + Vercel (frontend) |

---

## Local Development

### Prerequisites
- Python 3.8+ and pip
- Node.js 18+
- ~3GB disk space for model files

### Backend

```bash
cd backend

# Install dependencies
pip install -r requirements.txt

# Download word vectors (~2.5GB total, one-time)
cd .. && bash scripts/download_models.sh

# Start the API (will parse + cache vectors on first run, ~2 min)
cd backend
uvicorn main:app --reload
```

`MODEL_CACHE_DIR` defaults to `~/.amtza/models` locally — matching where `download_models.sh` saves the vectors. Only set it explicitly in production (e.g. Railway's mounted volume, see Deployment below).

The backend runs on http://localhost:8000. First startup downloads and parses the word vectors — subsequent starts load the cached `.npy` files in ~3 seconds.

### Frontend

```bash
cd frontend
npm install
npm run dev
```

Open http://localhost:5173. The Vite proxy forwards API calls to `localhost:8000`.

### Tests

The backend's game logic — win detection, the homing-threshold decay, and the
message tiers — has a unit-test suite that needs no models:

```bash
cd backend
./venv/bin/python -m unittest discover -s test -v
```

### Performance & startup notes

- **Fast guesses (~20ms).** Two things make that possible. The word-quality filter
  is precomputed over the whole vocabulary once at load and cached to disk
  (`{lang}_v8_good.npy` — the version suffix is bumped whenever the filters change,
  so a stale mask can never survive a deploy). And the nearest-neighbour search is
  a single matmul: every vector is L2-normalised, so a dot product *is* the cosine,
  which is ~30x faster than the equivalent scikit-learn query at this vocabulary
  size. A hint costs ~26ms, since it also computes the answer in order to avoid
  giving it away.
- **Non-blocking startup (~2 min, once).** Models load in a background task, so the
  app and `/health` come up immediately; game endpoints return `503` until they
  finish. On a first boot the vectors are **streamed** and parsed on the fly, stopping
  at the 150k most frequent words rather than downloading the full ~2.5GB — no
  scratch disk needed. Every boot after that loads the cached `.npy` files in seconds.

---

## Deployment

The two halves deploy separately: a static frontend on a CDN, and the Python API
on a box with real memory. **The backend cannot run on Netlify/Vercel** — it keeps
~350MB of word vectors resident, which serverless functions don't allow.

### Backend — Hugging Face Spaces (free)

Measured requirements: **~500MB RAM** in steady state (both languages loaded).
That rules out the common free tiers (Render free is 512MB and would OOM), but
Hugging Face Spaces gives **2 vCPU / 16GB RAM free**, no card required — it's
built for exactly this kind of model-backed service. The `Dockerfile` in the repo
root is already Spaces-shaped (non-root user, port 7860).

1. [huggingface.co/new-space](https://huggingface.co/new-space) → name it `amtza`,
   pick **Docker → Blank**, visibility **Public** (free tier), create.
2. Push this repo to the Space:
   ```bash
   git remote add hf https://huggingface.co/spaces/<your-username>/amtza
   git push hf master:main
   ```
   (Authenticate with a token from huggingface.co/settings/tokens, `write` scope.)
3. Once built, the API is at `https://<your-username>-amtza.hf.space`.
4. Add `ALLOWED_ORIGIN=https://your-site.netlify.app` under the Space's
   **Settings → Variables and secrets**.

Boot takes ~2 minutes: `/health` answers immediately and the game endpoints return
`503` while the vectors stream in. Free Spaces sleep after 48h idle and wake on the
next visit. Storage is ephemeral, which is fine here — nothing is downloaded to
disk, the vectors are streamed and parsed straight into memory.

*(Paid alternative, if you ever want zero cold starts: Railway with a 1GB volume,
`MODEL_CACHE_DIR=/data/models`, ~$5/mo — `railway.json` is already in the repo.)*

### Frontend — Netlify

`netlify.toml` in the repo root already sets the base/build/publish and the SPA
redirect, so there is nothing to configure by hand.

1. Netlify → **Add new site → Import an existing project** → pick this repo
2. Site settings → **Environment variables** → add
   `VITE_API_URL = https://your-backend.up.railway.app` (no trailing slash)
3. Deploy

Vite inlines env vars at **build** time, so after changing `VITE_API_URL` you must
trigger a redeploy for it to take effect.

> Deploy the backend first — you need its URL for `VITE_API_URL`, and the backend
> needs the Netlify URL for `ALLOWED_ORIGIN`. Set `ALLOWED_ORIGIN` once Netlify
> gives you the site URL, then redeploy the frontend.

---

## API Reference

| Endpoint | Description |
|----------|-------------|
| `GET /health` | `{status, models_loaded}` |
| `GET /pair?lang=he\|en` | Random starting word pair |
| `POST /guess` | Submit a guess, get computer's answer + scores |
| `GET /validate/{word}` | Check if a word is in vocabulary |
| `POST /hint` | Get 3 hint words near the midpoint |

---

## Project Structure

```
amtza/
├── backend/
│   ├── main.py          API routes
│   ├── embeddings.py    fastText loading + midpoint math
│   ├── game.py          win detection + funny messages
│   └── word_pairs.py    curated starting pairs
├── frontend/
│   └── src/
│       ├── App.jsx      state machine (loading→idle→guessing→revealing→won)
│       ├── api.js       all API calls
│       └── components/  WordPair, GuessInput, RevealCard, SimilarityMeter...
└── scripts/
    └── download_models.sh
```

---

## License

MIT
