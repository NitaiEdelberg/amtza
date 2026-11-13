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
If you circle the same territory for a while, a gentle "homing" mechanism relaxes
the match bar each round so every game converges.

### How the computer picks its middle

Two signals, because either one alone gets it wrong:

1. **Word vectors** (fastText) find candidates related to both words, scored by the
   weaker of the two similarities so the answer is balanced between them.
2. **Everyday associations** (`backend/data/{lang}_associations.tsv`): for every word
   the computer may say, its category and the words people think of first. A word
   people link to *both* sides gets a bonus.

The second exists because vectors measure which words appear together in text, not
what a person reaches for. For apple + tree people say *fruit*; the vectors rank fig,
olive and plum above it, because members of a category sit closer to each other than
to its name. For holiday + candles every Israeli says *Hanukkah*; the vectors said
*custom*. The associations were written per word, never per pair, so nothing in them
was fitted to the test pairs below.

The computer also never hands back a reshaped copy of a word already played
(hero → heroine, musical → singer, wheels → wheel), and a plural or "the-" form of
the same word counts as the same word (ילדים = ילד, הים = ים, apples = apple).

`scripts/eval_human.py` measures how often the computer's word is one of the three
answers a typical speaker would give, over 313 labelled pairs.

---

## The playable word list

`backend/data/he_playable.txt` and `en_playable.txt` are the pool the computer may
answer from — about 2,200 Hebrew and 2,500 English everyday nouns and adjectives,
checked word by word for real, common, correctly spelled words.

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

143 backend tests, none of which need the models, and 43 frontend tests:

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
./backend/venv/bin/python scripts/eval_quality.py --games-per-pair 4
```

Two harnesses judge the computer's choices, and a change to the scoring or the word
lists should be run through both:

```bash
./backend/venv/bin/python scripts/eval_human.py            # does it say what people say?
./backend/venv/bin/python scripts/eval_human.py --misses he
./backend/venv/bin/python scripts/eval_quality.py --games-per-pair 3
./backend/venv/bin/python scripts/build_associations.py    # after editing a word list
```

`eval_human.py` scores the computer's word against three human answers per pair.

**CI** (`.github/workflows/`): `ci.yml` runs the unit tests, lint and build on every
push and PR. `eval.yml` runs whenever `backend/` or `scripts/` change: it loads the
real models from the `models-v1` Release, fails if the association map is stale,
fails if any split of `eval_human.py` matches people on more than 2 fewer pairs than
`scripts/data/eval_baseline.json`, and posts the convergence numbers to the run
summary. After an intended improvement, refresh the baseline with
`scripts/eval_human.py --write-baseline` and commit it with the change.
`eval_quality.py` is the one for convergence and variety.
It reports three things, not just speed, because the two ways a pool can be wrong
pull in opposite directions — too obscure reads as *weird*, too small reads as
*repetitive*:

Measured on 2026-11-13, before and after adding the association map:

| | he before | he after | en before | en after |
|---|---|---|---|---|
| **computer says a human answer** (`eval_human.py`, starting pairs) | 40% | **51%** | 65% | **73%** |
| same, mid-game pairs with a clear answer | 10% | **19%** | 28% | **44%** |
| **play-tester agent** games won | 3/7 | **7/8** | 7/7 | **8/8** |
| play-tester agent, average rounds | ~13 | **~6.7** | ~5.6 | **~3.3** |
| simulated player, converge within 30 rounds | 71.7% | 63.2% | 91.0% | 88.6% |
| simulated player, median rounds | 10 | 13 | 7 | 7 |
| distinct answers | 23% | 23% | 36% | 36% |

The last block moved the wrong way for Hebrew, and that is expected rather than
ignored: `eval_quality.py`'s stand-in player picks by cosine, exactly as the old
computer did, so a computer that answers more like a person agrees with it less.
The play-tester (an agent told to play as an ordinary Israeli and never shown the
code) is the closer proxy for a real player, and it improved in both languages.
All of these are model proxies for people; a few real games are still worth more.

**Why Hebrew still trails English.** The Hebrew vectors come from Wikipedia, an
encyclopedia, while English uses web text. Hebrew near-synonyms land at 0.25–0.66
(`ילד`/`נער` 0.66, `בית`/`דירה` 0.25), so a near-synonym rarely clears the win bar,
and lowering it does not work: at 0.72–0.80 Hebrew already pairs `אדום`/`כחול`,
`לבן`/`שחור` and `כדורגל`/`כדורסל`, so any looser bar calls different things the
same. The levers that do work are making the computer say what a person would
(the association map) and counting a plural or "the-" form as the same word.

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

### Concurrency

Measured, since "will it survive being shared in a group chat" is the question
that matters. A guess costs **2.0ms of CPU** with BLAS pinned to one thread —
without the pinning in `main.py` the same guess costs 61ms of CPU across sixteen
cores, which is why that pinning is there. End to end, including FastAPI and JSON,
a request costs ~7.7ms of CPU.

| | |
|---|---|
| 40 simultaneous players, one core | p50 20ms, p99 103ms, 0 errors |
| 100 simultaneous players, one core | p50 257ms, p99 370ms, 0 errors |
| sustained capacity at 0.1 CPU | ~13 req/s |

40 players guessing every 20 seconds is 2 req/s — about 15% of a free instance.
Memory doesn't scale with players either: the model is shared, and the whole
process sits at 290MB. **The thing that would actually break a "40 people at once"
moment is the cold start, not the load** — if the instance is asleep when a link
is shared, everyone waits out one wake-up together. That is what the keep-alive
below is for.

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

## Launch checklist (sharing it publicly)

Measured on the live free instance (0.1 CPU, Oregon) on 2026-11-13: no errors with
40 simultaneous simulated players, but the server tops out around 12 guesses a
second, so past ~25 people actively playing at once every guess waits 2-6s.
About 0.4s of every request is the trip to Oregon. The free tier is enough for a
LinkedIn post; these steps make the first impression good:

1. **Check the preview.** Paste the link into LinkedIn's
   [Post Inspector](https://www.linkedin.com/post-inspector/). LinkedIn caches
   previews, so do this *before* posting, and again after any change to
   `og-image.png` or the meta tags.
2. **Play a full game on your phone**, in both languages. Most clicks come from the
   LinkedIn app's in-app browser.
3. **Turn on launch mode** right before posting: Actions → `launch-mode` → Run
   workflow (up to 6h; run again to extend). A sleeping free instance makes the
   first visitor wait about a minute. It spends the shared 750h Render budget, so
   don't leave it on.
4. **Watch it.** Render's logs show `gamelog:` lines and any errors; the
   Supabase `rounds` table fills as people play.

What protects the shared server: per-IP limits (`backend/ratelimit.py`: bursts of
20 guesses, then 60/min, generous on purpose because offices share one IP), a
15s timeout with one automatic retry in the client, and plain "the server is busy"
messages instead of a spinner that never ends. If it outgrows the free tier,
Render's Starter plan ($7/mo) removes the sleep and gives ~5x the CPU.

### Game data (Supabase)

Optional and off by default. When on, every round is stored anonymously (a random
per-game id, the language, the words on screen, both guesses, their similarity,
and whether it was won: no IP, no user agent, no account), so real games can check
what the model-based evals only approximate. Setup:

1. In Supabase, run `supabase/schema.sql` in the SQL editor. It enables row-level
   security with no policies, so the public key can't read or write the table.
2. In Render → amtza-api → Environment, set `SUPABASE_URL`
   (`https://<project>.supabase.co`) and `SUPABASE_KEY` (the **secret** key).
   Never put the secret key in Netlify; the frontend doesn't need it.
3. Redeploy. The log shows `gamelog: on`.

The welcome screen tells players what is kept. If the stored fields ever change,
change that sentence too.

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
│   ├── word_pairs.py    curated starting pairs (105 he + 108 en)
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
    ├── eval_quality.py  convergence + variety + weirdness metrics
    └── playtest.py      audition pairs / inspect the computer's picks
```

---

## License

MIT
