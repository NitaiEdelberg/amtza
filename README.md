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

The computer always plays the mathematical vector midpoint. The challenge is thinking like the algorithm.

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
MODEL_CACHE_DIR=/data/models uvicorn main:app --reload
```

The backend runs on http://localhost:8000. First startup downloads and parses the word vectors — subsequent starts load the cached `.npy` files in ~3 seconds.

### Frontend

```bash
cd frontend
npm install
npm run dev
```

Open http://localhost:5173. The Vite proxy forwards API calls to `localhost:8000`.

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
