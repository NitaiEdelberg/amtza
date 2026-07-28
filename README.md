# אמצע 🎯

**A cooperative semantic word game** — you and the computer both try to find the word that sits *in the middle* of two given words. Your guesses form the next pair. Keep going until you both land on the same word.

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

- **Fast guesses.** The word-quality filter is precomputed over the whole vocabulary
  once at load and cached to disk (`{lang}_v3_good.npy`), so each `/guess` is just a
  few vector dot products (~0.2s) rather than thousands of per-candidate lookups.
- **Non-blocking startup.** Models load in a background task, so the app (and
  `/health`) come up immediately. Game endpoints return `503` until the models
  finish. The **first-ever** boot downloads ~2.5GB of vectors and builds the caches
  (several minutes); every boot after that loads the cache in seconds.

---

## Deployment

### Railway (Backend)

1. Create a new Railway project, link this repo
2. Set the **root directory** to `backend`
3. Create a **Volume** and mount it at `/data`
4. Add environment variables:
   - `MODEL_CACHE_DIR=/data/models`
   - `ALLOWED_ORIGIN=https://your-app.vercel.app`
5. Deploy — first start downloads models (~5-10 min), then the health check passes

### Vercel (Frontend)

1. Import this repo on Vercel
2. Set **root directory** to `frontend`
3. Add environment variable:
   - `VITE_API_URL=https://your-railway-app.railway.app`
4. Deploy

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
