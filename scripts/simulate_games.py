"""Simulate many Amtza games to measure rounds-to-convergence.

The "computer" side uses the production `find_best_middle` (always the single
best-scoring midpoint word). The "player" side samples from a pool of plausible
midpoint words, weighted toward higher scores but with randomness — emulating a
human who has good semantic intuition but doesn't compute exact cosine scores.

Usage:
    venv/bin/python scripts/simulate_games.py [--games-per-pair N] [--seed S] [--max-rounds M]
"""
import argparse
import functools
import os
import random
import statistics
import sys
import time

print = functools.partial(print, flush=True)

BACKEND_DIR = os.path.join(os.path.dirname(__file__), "..", "backend")
sys.path.insert(0, os.path.abspath(BACKEND_DIR))
os.environ.setdefault("MODEL_CACHE_DIR", os.path.expanduser("~/.amtza/models"))

import numpy as np

from embeddings import (
    WordNotFoundError,
    _is_good_idx,
    _nearest_indices,
    _phrase_tokens,
    find_best_middle,
    get_word_vector,
    load_or_download_sync,
    normalize_word,
    phrase_vec,
)
from game import (check_win, _effective_threshold, WIN_THRESHOLD,
                  HOMING_GRACE_ROUNDS, HOMING_DECAY_PER_ROUND, HOMING_MIN_THRESHOLD)
from word_pairs import STARTING_PAIRS


def simulated_player_guess(space, word1, word2, exclude, rng, pool_size=20, top_k=12):
    """Human-like guess: weighted random pick from a pool of plausible middle words."""
    v1 = phrase_vec(space, word1)
    v2 = phrase_vec(space, word2)
    midpoint = v1 + v2
    norm = np.linalg.norm(midpoint)
    if norm > 0:
        midpoint = midpoint / norm
    midpoint = midpoint.astype(np.float32)

    n_candidates = min(400, len(space.words))
    # Same fast paths the game itself uses: a matmul for the neighbour search and
    # the precomputed quality mask. Calling _is_good_suggestion per candidate here
    # re-ran the expensive contamination k-NN and made simulation unusably slow.
    indices = _nearest_indices(space, midpoint, n_candidates)

    candidates = []
    for idx in indices:
        word = space.words[idx]
        if word in exclude or not _is_good_idx(space, idx):
            continue
        w_vec = space.matrix[idx]
        s1 = float(np.dot(w_vec, v1))
        s2 = float(np.dot(w_vec, v2))
        score = min(s1, s2)
        candidates.append((word, score))
        if len(candidates) >= pool_size:
            break

    if not candidates:
        return None

    top = candidates[:top_k]
    words_, scores_ = zip(*top)
    weights = [s - min(scores_) + 0.05 for s in scores_]
    return rng.choices(words_, weights=weights, k=1)[0]


def simulate_game_trace(space, word1, word2, lang, rng, max_rounds):
    """Play out a full game (ignoring the win condition) and record, for each round,
    whether the guesses were identical and their cosine similarity. This lets us
    retroactively compute "round of convergence" for *any* WIN_THRESHOLD without
    re-simulating — identical-word rounds always win regardless of threshold."""
    pair_tokens = _phrase_tokens(space, word1) | _phrase_tokens(space, word2)
    used = set(pair_tokens)
    w1, w2 = word1, word2
    trace = []  # list of (is_identical, similarity)

    for _ in range(max_rounds):
        exclude = set(used)
        try:
            computer_guess = find_best_middle(space, w1, w2, exclude=exclude)
        except WordNotFoundError:
            return trace
        player_guess = simulated_player_guess(space, w1, w2, exclude, rng)
        if computer_guess is None or player_guess is None:
            return trace

        cv = get_word_vector(space, computer_guess)
        pv = get_word_vector(space, player_guess)
        if cv is None or pv is None:
            return trace

        identical = player_guess.lower() == computer_guess.lower()
        sim = float(np.dot(pv, cv))
        trace.append((identical, sim))

        if identical:
            return trace

        used.add(normalize_word(player_guess, lang))
        used.add(normalize_word(computer_guess, lang))
        w1, w2 = player_guess, computer_guess

    return trace


def rounds_to_converge(trace, threshold=None):
    """If threshold is None, use the production "homing" curve (_effective_threshold) —
    a fixed bar up to round 10, then gradually relaxing. Otherwise use a flat threshold
    (useful for comparing against the pre-homing behaviour)."""
    for round_num, (identical, sim) in enumerate(trace, start=1):
        bar = _effective_threshold(round_num) if threshold is None else threshold
        if identical or sim > bar:
            return round_num
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--games-per-pair", type=int, default=15)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--max-rounds", type=int, default=30)
    ap.add_argument("--lang", choices=["he", "en", "both"], default="both")
    ap.add_argument("--thresholds", type=str, default="",
                    help="Optional comma-separated flat WIN_THRESHOLD values for comparison "
                         "against the production homing curve, e.g. '0.80,0.75,0.72'")
    args = ap.parse_args()

    thresholds = [float(t) for t in args.thresholds.split(",") if t.strip()]
    rng = random.Random(args.seed)

    langs = ["he", "en"] if args.lang == "both" else [args.lang]
    print(f"Loading embedding spaces: {langs} ...")
    spaces = {lang: load_or_download_sync(lang) for lang in langs}
    print("Loaded.\n")

    pairs = [p for p in STARTING_PAIRS if p["language"] in langs]
    t_start = time.time()
    n_done = 0
    n_total = len(pairs) * args.games_per_pair
    traces = []  # (word1, word2, trace)
    for pair in pairs:
        space = spaces[pair["language"]]
        for g in range(args.games_per_pair):
            t0 = time.time()
            trace = simulate_game_trace(space, pair["word1"], pair["word2"], pair["language"], rng, args.max_rounds)
            dt = time.time() - t0
            n_done += 1
            elapsed = time.time() - t_start
            eta = elapsed / n_done * (n_total - n_done)
            r_homing = rounds_to_converge(trace)
            print(f"  [{n_done}/{n_total}] {pair['word1']}+{pair['word2']} game {g+1}: "
                  f"{'rounds=' + str(r_homing) if r_homing else 'no-converge'} "
                  f"len={len(trace)} ({dt:.1f}s) elapsed={elapsed:.0f}s eta={eta:.0f}s")
            traces.append((pair["word1"], pair["word2"], trace))

    def report(label, rounds_fn):
        all_rounds = []
        non_converged = []
        per_pair = {}
        for w1, w2, trace in traces:
            r = rounds_fn(trace)
            key = (w1, w2)
            per_pair.setdefault(key, []).append(r)
            if r is None:
                non_converged.append(key)
            else:
                all_rounds.append(r)

        print(f"\n--- {label} ---")
        total = len(all_rounds) + len(non_converged)
        print(f"Converged: {len(all_rounds)}/{total}  "
              f"({100*len(non_converged)/total:.1f}% never converged within {args.max_rounds} rounds)")
        if all_rounds:
            print(f"avg={statistics.mean(all_rounds):.2f}  median={statistics.median(all_rounds):.1f}  "
                  f"max={max(all_rounds)}  p95={sorted(all_rounds)[int(len(all_rounds)*0.95)]}")
            over_20 = [r for r in all_rounds if r > 20]
            print(f"Games > 20 rounds: {len(over_20)} ({100*len(over_20)/total:.1f}% of all games)")
        worst = sorted(per_pair.items(), key=lambda kv: -statistics.mean([x for x in kv[1] if x] or [0]))[:6]
        print("Worst pairs:")
        for (w1, w2), rs in worst:
            valid = [x for x in rs if x]
            avg = statistics.mean(valid) if valid else float("nan")
            n_fail = sum(1 for x in rs if x is None)
            print(f"  {w1:>12} + {w2:<12}  avg={avg:5.1f}  max={max(valid) if valid else '-':>3}  fails={n_fail}/{len(rs)}")

    print("\n=== PRODUCTION (homing curve) ===")
    # Label read from the live constants — a hardcoded one silently goes stale
    # the moment the win bar is retuned.
    report(f"homing curve (bar={WIN_THRESHOLD}, grace={HOMING_GRACE_ROUNDS}, "
           f"decay={HOMING_DECAY_PER_ROUND}/round, floor={HOMING_MIN_THRESHOLD})",
           lambda trace: rounds_to_converge(trace))

    if thresholds:
        print("\n=== FLAT-THRESHOLD COMPARISON (pre-homing behaviour) ===")
        for threshold in thresholds:
            report(f"flat WIN_THRESHOLD = {threshold}", lambda trace, t=threshold: rounds_to_converge(trace, t))


if __name__ == "__main__":
    main()
