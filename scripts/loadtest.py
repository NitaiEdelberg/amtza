"""Simulated players against a running API, paced like people.

A request-per-second benchmark says little about a game: people think, type,
read the reveal and start over. Each simulated player here does what the
frontend does for a person:

    /pair -> (think 4-9s, type: two /validate calls, /guess, read 3-5s) x rounds
           -> sometimes /hint -> new game after a win or 8 rounds

and every request's latency and status is recorded. Stdlib only, so it runs on a
bare CI runner.

ONE IP IS NOT 100 PLAYERS. The API rate-limits per IP (backend/ratelimit.py), so
100 simulated players from one machine measure the limiter, not the server. The
loadtest workflow splits players across parallel runners, each with its own IP,
at a per-runner count that stays under the per-IP limits.

Usage:
    python scripts/loadtest.py --api https://amtza-api.onrender.com --players 10 --minutes 3
    python scripts/loadtest.py ... --out shard.json      # raw results for merging
    python scripts/loadtest.py --merge shard-*.json      # one report from many shards
"""
import argparse
import glob
import json
import random
import threading
import time
import urllib.error
import urllib.parse
import urllib.request

WORDS = {
    "he": ["אור", "מים", "בית", "אהבה", "ילד", "שמש", "כסף", "ים", "עץ", "חבר", "אוכל", "משפחה",
           "עבודה", "זמן", "מוזיקה", "ספר", "דרך", "לב", "חיה", "שמיים", "פרח", "אש", "רוח", "כוכב"],
    "en": ["light", "water", "house", "love", "child", "sun", "money", "sea", "tree", "friend", "food",
           "family", "work", "time", "music", "book", "road", "heart", "animal", "sky", "flower",
           "fire", "wind", "star"],
}


class Recorder:
    def __init__(self):
        self.lock = threading.Lock()
        self.rows = []   # (kind, status, seconds)

    def add(self, kind, status, seconds):
        with self.lock:
            self.rows.append((kind, status, round(seconds, 4)))


def call(api, rec, kind, path, body=None):
    url = api.rstrip("/") + path
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, headers={"content-type": "application/json"} if data else {})
    t = time.time()
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            payload = json.loads(r.read())
            rec.add(kind, r.status, time.time() - t)
            return payload
    except urllib.error.HTTPError as e:
        rec.add(kind, e.code, time.time() - t)
    except Exception:
        rec.add(kind, "error", time.time() - t)
    return None


def player(api, rec, deadline, rng):
    while time.time() < deadline:
        lang = rng.choice(["he", "en"])
        pair = call(api, rec, "pair", f"/pair?lang={lang}")
        if not pair:
            time.sleep(5)
            continue
        w1, w2 = pair["word1"], pair["word2"]
        used = [w1, w2]
        hinted = False
        for rnd in range(1, 9):
            if time.time() >= deadline:
                return
            time.sleep(rng.uniform(4, 9))                       # think
            if not hinted and rng.random() < 0.15:
                hinted = True
                call(api, rec, "hint", "/hint", {"word1": w1, "word2": w2})
            options = [w for w in WORDS[lang] if w not in used] or WORDS[lang]
            guess = rng.choice(options)
            call(api, rec, "validate", "/validate/" + urllib.parse.quote(guess[:3]))   # typing
            time.sleep(0.4)
            call(api, rec, "validate", "/validate/" + urllib.parse.quote(guess))
            r = call(api, rec, "guess", "/guess", {"word1": w1, "word2": w2, "player_guess": guess,
                                                     "round_num": rnd, "used_words": used})
            time.sleep(rng.uniform(3, 5))                       # read the reveal
            if not r or r.get("is_won"):
                break
            used += [r["player_guess"], r["computer_guess"]]
            w1, w2 = r["new_pair"]


def run(api, players, minutes, ramp, seed):
    rec = Recorder()
    deadline = time.time() + ramp + minutes * 60
    threads = []
    for i in range(players):
        rng = random.Random(seed * 1000 + i)
        t = threading.Thread(target=player, args=(api, rec, deadline, rng), daemon=True)
        t.start()
        threads.append(t)
        time.sleep(ramp / max(players, 1))   # stagger arrivals
    for t in threads:
        t.join(timeout=minutes * 60 + ramp + 60)
    return rec.rows


def report(rows, players, seconds):
    def pct(xs, p):
        xs = sorted(xs)
        return xs[min(len(xs) - 1, int(len(xs) * p))] if xs else float("nan")
    lines = [f"### Load test: {players} players, {len(rows)} requests over {seconds / 60:.1f} min "
             f"({len(rows) / seconds:.1f} req/s)", "",
             "| request | count | ok | p50 | p95 | max | non-2xx |", "|---|---|---|---|---|---|---|"]
    for kind in ("pair", "validate", "guess", "hint"):
        sel = [r for r in rows if r[0] == kind]
        ok = [r[2] for r in sel if r[1] == 200]
        bad = {}
        for r in sel:
            if r[1] != 200:
                bad[str(r[1])] = bad.get(str(r[1]), 0) + 1
        lines.append(f"| {kind} | {len(sel)} | {len(ok)} | {pct(ok, .5) * 1000:.0f}ms | "
                     f"{pct(ok, .95) * 1000:.0f}ms | {max(ok, default=0) * 1000:.0f}ms | "
                     f"{', '.join(f'{k}: {v}' for k, v in sorted(bad.items())) or '-'} |")
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--api", default="https://amtza-api.onrender.com")
    ap.add_argument("--players", type=int, default=10)
    ap.add_argument("--minutes", type=float, default=3)
    ap.add_argument("--ramp", type=float, default=30, help="seconds over which players arrive")
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--out", help="write raw results here (JSON) for --merge")
    ap.add_argument("--merge", nargs="+", help="combine shard files into one report")
    args = ap.parse_args()

    if args.merge:
        rows, players, seconds = [], 0, 0
        for path in sorted(p for pattern in args.merge for p in glob.glob(pattern)):
            d = json.load(open(path))
            rows += [tuple(r) for r in d["rows"]]
            players += d["players"]
            seconds = max(seconds, d["seconds"])
        print(report(rows, players, seconds))
        return

    t0 = time.time()
    rows = run(args.api, args.players, args.minutes, args.ramp, args.seed)
    seconds = time.time() - t0
    print(report(rows, args.players, seconds))
    if args.out:
        json.dump({"players": args.players, "seconds": seconds, "rows": rows}, open(args.out, "w"))


if __name__ == "__main__":
    main()
