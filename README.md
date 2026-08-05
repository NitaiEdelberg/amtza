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

<!-- The YAML block above is Hugging Face Space metadata, kept in case the backend
     is ever hosted there. It is inert on GitHub, which renders it as a small table.
     The live backend runs on Render — see Deployment. -->


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
| Deployment | Render (backend) + Netlify (frontend) |

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

`MODEL_CACHE_DIR` defaults to `~/.amtza/models` locally — matching where `download_models.sh` saves the vectors. Only set it explicitly in production (see Deployment below).

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

### Backend — Render (free)

**Memory is the whole story.** Both languages resident used to cost ~500MB, which
is over the 512MB a free container gets. Three changes brought the peak to ~350MB:

| | before | after |
|---|---|---|
| Matrix storage | float32, 348MB | **float16, 174MB** |
| Fresh parse peak | 398MB (list + `vstack`) | **226MB** (one preallocated buffer, rows normalised inline) |
| Language loading | both at once (`asyncio.gather`) | **one after the other** |

Half precision is safe here because every dot product still accumulates in float32:
the resulting cosine is accurate to ~7e-4, and the computer's pick was **identical on
all 33 starting pairs** in both languages. See `_STORE_DTYPE` in `backend/embeddings.py`.

1. Render → **New → Blueprint** → pick this repo. `render.yaml` sets the runtime,
   build/start commands and health check, so there is nothing to fill in.
2. Once it is live the API is at `https://<service-name>.onrender.com`.
3. Add `ALLOWED_ORIGIN=https://your-site.netlify.app` under **Environment**
   (exact origin, no trailing slash).

`/health` answers `200` immediately and reports `models_loaded`; the game endpoints
return `503` until the vectors are in. Free instances sleep after 15 minutes idle.

**Cold starts:** free instances have no persistent disk, so by default every wake-up
re-streams ~670MB of raw vectors and recomputes the good-word masks — minutes. To
avoid that, publish the finished caches (178MB) once and point the service at them:

```bash
./scripts/publish_model_cache.sh          # uploads to a GitHub Release
# then set on Render:
PREBUILT_CACHE_URL=https://github.com/<you>/amtza/releases/download/models-v1
```

Optional but strongly recommended — it is the difference between a wake-up measured
in minutes and one measured in seconds. `.github/workflows/keep-alive.yml` in the
sibling repo shows the cron trick for keeping the instance warm during the day.

*Not Hugging Face Spaces:* Spaces now requires a paid plan for anything that runs
compute (Gradio/Docker); only Static Spaces are free, and those cannot run Python.
The `Dockerfile` is still here and still correct if you ever want a container host.

### Frontend — Netlify

`netlify.toml` in the repo root already sets the base/build/publish and the SPA
redirect, so there is nothing to configure by hand.

1. Netlify → **Add new site → Import an existing project** → pick this repo
2. Site settings → **Environment variables** → add
   `VITE_API_URL = https://<service-name>.onrender.com` (no trailing slash)
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
