"""Measure answer quality, not just convergence.

`simulate_games.py` answers one question: how many rounds does a game take. That
is not enough to decide whether the computer's vocabulary should grow, because
the two ways a bigger pool can go wrong pull in opposite directions:

  * too obscure  — the extra words are ones nobody would offer, so the computer
                   starts saying things that feel random ("weird").
  * too narrow   — the pool is so small that the same handful of words come back
                   game after game ("predictable").

Both are measured here, alongside the convergence numbers, so a vocabulary
change can be judged on all three at once instead of on rounds alone.

DEFINITIONS (stated because they are judgement calls, not facts):

  weak-link    min(sim_to_word1, sim_to_word2) < WEAK_LINK. The answer is barely
               related to one of the two words on screen. This is what a player
               actually perceives as "huh?" — not rarity, but a word that doesn't
               connect to something they can see.

  obscure      the answer sits below the OBSCURE_RANK most frequent words in the
               corpus. A word a player has to look up reads as weird even when
               the vector maths is sound.

  concentration
               share of all answers taken by the 10 most-used ones, plus the
               count of distinct answers. A game whose computer says "מים" in a
               third of all rounds is repetitive however fast it converges.

THE PLAYER MODEL. The stand-in player picks a plausible middle word from the
PLAYER_VOCAB most frequent words in the language, weighted toward better ones.
That range matters: drawing from the curated list would let the player and the
computer share one small pool and flatter every convergence number, while
drawing from all 150k lets it "think" of corpus debris no human would type.

Usage:
    venv/bin/python scripts/eval_quality.py --games-per-pair 6
    venv/bin/python scripts/eval_quality.py --lang he --label "3k pool"
"""
import argparse
import functools
import json
import os
import random
import statistics
import sys
import time
from collections import Counter

print = functools.partial(print, flush=True)

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend")))
os.environ.setdefault("MODEL_CACHE_DIR", os.path.expanduser("~/.amtza/models"))

import numpy as np  # noqa: E402

from embeddings import (  # noqa: E402
    WordNotFoundError, _phrase_tokens, find_best_middle,
    get_word_vector, load_or_download_sync, normalize_word, phrase_vec,
)
from game import _effective_threshold  # noqa: E402
from word_pairs import STARTING_PAIRS  # noqa: E402

WEAK_LINK = 0.20
OBSCURE_RANK = 25_000
PLAYER_VOCAB = 30_000


class PlayerBrain:
    """The stand-in player's own view of the language.

    Holds the top PLAYER_VOCAB rows at float32. Upcasting once here rather than
    per call is the difference between a usable harness and a 10-minute wait: the
    stored matrix is float16, and `matrix @ vec` promotes the whole array on every
    single query.
    """

    def __init__(self, space):
        n = min(PLAYER_VOCAB, len(space.words))
        self.n = n
        self.matrix = space.matrix[:n].astype(np.float32)
        self.words = space.words[:n]

    def guess(self, space, v1, v2, midpoint, exclude, rng, pool=20, top_k=12):
        sims = self.matrix @ midpoint
        order = np.argpartition(-sims, min(400, self.n - 1))[:400]
        order = order[np.argsort(-sims[order])]
        cands = []
        for idx in order:
            word = self.words[idx]
            if word in exclude:
                continue
            row = self.matrix[idx]
            cands.append((word, min(float(row @ v1), float(row @ v2))))
            if len(cands) >= pool:
                break
        if not cands:
            return None
        top = cands[:top_k]
        words_, scores_ = zip(*top)
        weights = [s - min(scores_) + 0.05 for s in scores_]
        return rng.choices(words_, weights=weights, k=1)[0]


def play(space, brain, w1, w2, lang, rng, max_rounds, rank_of):
    """One game. Returns (rounds_to_converge|None, [answer records])."""
    used = set(_phrase_tokens(space, w1) | _phrase_tokens(space, w2))
    answers = []
    for rnd in range(1, max_rounds + 1):
        exclude = set(used)
        try:
            comp = find_best_middle(space, w1, w2, exclude=exclude)
        except WordNotFoundError:
            break
        if comp is None:
            break
        v1, v2 = phrase_vec(space, w1), phrase_vec(space, w2)
        mid = v1 + v2
        norm = np.linalg.norm(mid)
        mid = (mid / norm if norm else mid).astype(np.float32)

        cv = get_word_vector(space, comp)
        answers.append({
            "word": comp, "round": rnd,
            "min_sim": min(float(cv @ v1), float(cv @ v2)),
            "rank": rank_of.get(comp, 10**9),
        })

        player = brain.guess(space, v1, v2, mid, exclude, rng)
        if player is None:
            break
        pv = get_word_vector(space, player)
        if pv is None:
            break

        identical = player.lower() == comp.lower()
        if identical or float(pv @ cv) > _effective_threshold(rnd):
            return rnd, answers

        used.add(normalize_word(player, lang))
        used.add(normalize_word(comp, lang))
        w1, w2 = player, comp
    return None, answers


def evaluate(lang, games_per_pair, seed, max_rounds):
    space = load_or_download_sync(lang)
    brain = PlayerBrain(space)
    rank_of = {w: i for i, w in enumerate(space.words)}
    pairs = [(p["word1"], p["word2"]) for p in STARTING_PAIRS if p["language"] == lang]
    rng = random.Random(seed)

    rounds, all_answers, first_answers = [], [], {}
    n_fail = 0
    t0 = time.time()
    for i, (w1, w2) in enumerate(pairs, 1):
        for _ in range(games_per_pair):
            r, answers = play(space, brain, w1, w2, lang, rng, max_rounds, rank_of)
            if r is None:
                n_fail += 1
            else:
                rounds.append(r)
            all_answers.extend(answers)
            if answers:
                first_answers.setdefault((w1, w2), answers[0]["word"])
        if i % 10 == 0:
            print(f"    {lang}: {i}/{len(pairs)} pairs, {time.time()-t0:.0f}s")

    total_games = len(rounds) + n_fail
    words = [a["word"] for a in all_answers]
    counts = Counter(words)
    weak = [a for a in all_answers if a["min_sim"] < WEAK_LINK]
    obscure = [a for a in all_answers if a["rank"] > OBSCURE_RANK]

    return {
        "lang": lang,
        "pool_size": int(space.good_mask.sum()) if space.good_mask is not None else None,
        "pairs": len(pairs),
        "games": total_games,
        "converged_pct": 100 * len(rounds) / total_games if total_games else 0,
        "avg": statistics.mean(rounds) if rounds else None,
        "median": statistics.median(rounds) if rounds else None,
        "p95": sorted(rounds)[int(len(rounds) * 0.95)] if rounds else None,
        "over20_pct": 100 * sum(1 for r in rounds if r > 20) / total_games if total_games else 0,
        "answers": len(all_answers),
        "distinct": len(counts),
        "distinct_pct": 100 * len(counts) / len(all_answers) if all_answers else 0,
        "top10_share_pct": 100 * sum(c for _, c in counts.most_common(10)) / len(all_answers) if all_answers else 0,
        "weak_pct": 100 * len(weak) / len(all_answers) if all_answers else 0,
        "obscure_pct": 100 * len(obscure) / len(all_answers) if all_answers else 0,
        "top10": counts.most_common(10),
        "weakest": sorted({a["word"]: a["min_sim"] for a in weak}.items(), key=lambda kv: kv[1])[:12],
        "rarest": sorted({a["word"]: a["rank"] for a in obscure}.items(), key=lambda kv: -kv[1])[:12],
    }


def show(r):
    print(f"\n===== {r['lang']}  (pool {r['pool_size']:,} words, {r['pairs']} pairs, {r['games']} games) =====")
    print(f"  CONVERGENCE  {r['converged_pct']:.1f}%   median {r['median']}   avg {r['avg']:.2f}   "
          f"p95 {r['p95']}   >20 rounds {r['over20_pct']:.1f}%")
    print(f"  VARIETY      {r['distinct']:,} distinct answers out of {r['answers']:,} "
          f"({r['distinct_pct']:.1f}%);  top-10 words are {r['top10_share_pct']:.1f}% of all answers")
    print(f"  WEIRDNESS    weak-link {r['weak_pct']:.1f}%   obscure {r['obscure_pct']:.1f}%")
    print(f"  most repeated: {', '.join(f'{w}({c})' for w, c in r['top10'])}")
    if r["weakest"]:
        print(f"  weakest links: {', '.join(f'{w}({s:.2f})' for w, s in r['weakest'])}")
    if r["rarest"]:
        print(f"  rarest words:  {', '.join(f'{w}(#{k:,})' for w, k in r['rarest'])}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--games-per-pair", type=int, default=6)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--max-rounds", type=int, default=30)
    ap.add_argument("--lang", choices=["he", "en", "both"], default="both")
    ap.add_argument("--label", default="")
    ap.add_argument("--out", default="", help="write the raw numbers here as JSON for before/after diffing")
    args = ap.parse_args()

    langs = ["he", "en"] if args.lang == "both" else [args.lang]
    if args.label:
        print(f"### {args.label}")
    results = []
    for lang in langs:
        r = evaluate(lang, args.games_per_pair, args.seed, args.max_rounds)
        show(r)
        results.append(r)
    if args.out:
        with open(args.out, "w") as f:
            json.dump(results, f, ensure_ascii=False, indent=2)
        print(f"\nwrote {args.out}")


if __name__ == "__main__":
    main()
