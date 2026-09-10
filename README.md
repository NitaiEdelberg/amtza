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


**▶ Play it: [amtza.netlify.app](https://amtza.netlify.app)** (the backend sleeps on Render's free tier, so the first round of the day takes a few seconds to wake up)

> *Inspired by the Israeli word game "אמצע" played between friends.*

---

## How to Play

1. Two words appear on screen (e.g., **חביתה** ↔ **בן גוריון**)
2. You type a word you think is semantically "in the middle"
3. The computer also picks the word closest to the semantic midpoint
4. Both answers are revealed simultaneously
5. Your word + the computer's word form the **new pair**
6. Repeat until you both guess the same word — **you win!**

The computer plays the semantic midpoint, restricted to a curated list of everyday
words, so it won't throw junk tokens, proper nouns or grammatical fragments at you.
The challenge is thinking like the algorithm. If you circle the same territory for a
while, a gentle "homing" mechanism relaxes the match bar each round so every game
converges.

---

## The playable word list

`backend/data/he_playable.txt` and `en_playable.txt` are the pool the computer may
answer from — about 1,400 Hebrew and 1,800 English everyday nouns and adjectives.

They exist because filtering could not do this job. Morphological rules are good at
word *shape* and reliably reject בים, לעץ, נישואיה, running, biggest. They are
useless against everything else, and roughly 40% of what survived them in Hebrew was
proper nouns — גולדמן, ונצואלה, דורטמונד, פייסבוק — with no capital letter to give
them away, plus corpus debris like תרל, מטכ and בינוויקי. Every new offender meant
another name in another blocklist, and three rounds of that never converged.

Naming the pool instead ends the argument: a word is playable because it is on the
list. Adding one is a line in a text file; anything the model doesn't know is dropped
at load with a log line, so a typo is harmless.

**This list only governs what the computer answers.** Players may guess any word in
the 150k-word vocabulary.

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

114 backend tests, none of which need the models, and 29 frontend tests:

```bash
cd backend && ./venv/bin/python -m unittest discover -s test -v
cd frontend && npm test
```

To judge word quality by hand — the thing tests can't assert — use the playtest
harness, which loads the real vectors:

```bash
./backend/venv/bin/python scripts/playtest.py survey he      # every starting pair
./backend/venv/bin/python scripts/playtest.py inspect en cat dog
./backend/venv/bin/python scripts/playtest.py pairs he חורף קיץ  בוקר לילה
./backend/venv/bin/python scripts/simulate_games.py --games-per-pair 10
```

Last measured over 330 simulated games: 98% converge, median 4 rounds, average 6.0,
3.0% run past 20.

### Performance & startup notes

- **Fast guesses (~20ms).** Two things make that possible. The playable-word mask is
  a set lookup over the curated list at load, and the search only ever touches those
  ~1.5k rows rather than the full 150k. And the nearest-neighbour search is a single
  matmul: every vector is L2-normalised, so a dot product *is* the cosine, which is
  ~30x faster than the equivalent scikit-learn query at this vocabulary size. A hint
  costs ~26ms, since it also computes the answer in order to avoid giving it away.
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
every starting pair** in both languages. See `_STORE_DTYPE` in `backend/embeddings.py`.

1. Render → **New → Blueprint** → pick this repo. `render.yaml` sets the runtime,
   build/start commands and health check, so there is nothing to fill in.
2. Once it is live the API is at `https://<service-name>.onrender.com`.
3. Add `ALLOWED_ORIGIN=https://your-site.netlify.app` under **Environment**
   (exact origin, no trailing slash).

`/health` answers `200` immediately and reports which languages are ready
(`{"languages": ["he"]}`); the game endpoints return `503` for a language that isn't
in yet. Free instances sleep after 15 minutes idle.

**Cold starts:** free instances have no persistent disk, so by default every wake-up
re-streams ~670MB of raw vectors and re-parses them — minutes. To avoid that,
publish the finished caches (178MB) once and point the service at them:

```bash
./scripts/publish_model_cache.sh          # uploads to a GitHub Release
# then set on Render:
PREBUILT_CACHE_URL=https://github.com/<you>/amtza/releases/download/models-v1
```

> **The cache filenames are versioned, and the version just changed to `v4`.** A
> release holding `*_v3.npy` will be ignored, and every cold start will re-stream
> and re-parse the raw vectors. Re-run `publish_model_cache.sh` after deploying
> this change.

### Not being asleep in the first place

`.github/workflows/keep-alive.yml` pings `/health` every ten minutes between 06:00
and 23:00 Israel time. That window is deliberate: a free instance gets 750 hours a
month against a 730-hour month, so a 24/7 ping spends the whole allowance on one
service. ~17h/day is about 520 hours and covers every plausible player.

Point it at your own API by setting a repository variable `API_URL` (Settings →
Secrets and variables → Actions → Variables); it falls back to the URL in the file.

The frontend does its part too: the welcome screen renders immediately and the
health poll wakes the backend while the player reads the rules, so the wait only
becomes visible if they press Play before it finishes. Readiness is reported per
language, so a Hebrew game can start before English has loaded.

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

## Search and ads

### Being findable

`frontend/index.html` carries the title, description, canonical, `hreflang`,
Open Graph / Twitter tags and JSON-LD (`VideoGame` + `HowTo`). A `<noscript>` block
and the `SiteFooter` component supply the actual prose — a game board is otherwise
two runtime-generated nouns and a score, which gives a crawler nothing to index.

`public/robots.txt` and `public/sitemap.xml` are served as-is. The deployed origin is
baked into all three files (canonical, hreflang, og:image, JSON-LD `@id`, sitemap
`<loc>`) because crawlers read them without running the app. Move domains with:

```bash
./scripts/set_site_url.sh https://yourdomain.com
```

Regenerate the link-preview card after changing the title or tagline:

```bash
backend/venv/bin/pip install Pillow      # not a runtime dependency
backend/venv/bin/python scripts/make_og_image.py
```

Then, once deployed: submit the sitemap in Google Search Console, and request
indexing for the URL. Nothing gets crawled just because it exists.

### Ads

`AdSlot` renders **nothing** unless both are set at build time in Netlify:

| Variable | Value |
|---|---|
| `VITE_ADSENSE_CLIENT` | `ca-pub-…` |
| `VITE_ADSENSE_SLOT` | the ad unit's slot ID |

It appears below the board from round two, and below the New Game button on the win
screen — never above a button, which is how accidental clicks and invalid-traffic
bans happen. The AdSense script loads lazily on first render, so a visitor who never
finishes a round never pays for it, and an ad blocker leaves the reserved space
empty rather than breaking the game.

**A custom domain is a hard prerequisite, not a nice-to-have.** Since 2023 AdSense
verifies ownership at the *parent domain*, and approves subdomains by inheriting the
parent's status. The parent of `amtza.netlify.app` is `netlify.app`, which belongs to
Netlify — there is no DNS record to add and no root page to put the verification
snippet on, so it can never be approved. Same reason `mysite.wordpress.com` can't run
AdSense. Buy a domain, run `./scripts/set_site_url.sh https://yourdomain.com`, then
apply.

The other thing: apply *after* deploying. AdSense wants a site with real content, and
"low value content" is the standard first rejection.

---

## API Reference

| Endpoint | Description |
|----------|-------------|
| `GET /health` | `{status, models_loaded, languages}` — `languages` lists what is playable now |
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
│   ├── word_pairs.py    curated starting pairs (38 he + 42 en)
│   └── data/            he_playable.txt, en_playable.txt — the answer pool
├── frontend/
│   ├── public/          robots.txt, sitemap.xml, ads.txt, og-image.png
│   └── src/
│       ├── App.jsx      state machine (idle→guessing→revealing→won)
│       ├── api.js       all API calls
│       └── components/  WordPair, GuessInput, AdSlot, SiteFooter...
├── .github/workflows/
│   └── keep-alive.yml   pings /health so the free instance doesn't sleep
└── scripts/
    ├── download_models.sh
    ├── make_og_image.py
    └── playtest.py      audition pairs / inspect the computer's picks
```

---

## License

MIT
