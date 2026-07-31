"""Hand play-test harness — a real human (me) supplies the guesses.

Two modes:
  inspect  — for a pair, show the computer's middle-word pick and the pool of
             candidates it chose from, with each candidate's min(sim_w1, sim_w2).
             Lets me judge word quality / whether the pick "makes sense".
  play     — play a full game from a start pair using MY list of guesses. The
             pair evolves as (my_guess, computer_guess). find_best_middle is
             deterministic, so extending the guess list replays identically; when
             my guesses run out it prints the current pair + candidates and stops
             so I can decide the next move.

Usage:
    venv/bin/python scripts/playtest.py inspect he שמש ירח
    venv/bin/python scripts/playtest.py play he שמש ירח -- שקיעה אור כוכב
"""
import functools
import os
import sys

print = functools.partial(print, flush=True)

BACKEND_DIR = os.path.join(os.path.dirname(__file__), "..", "backend")
sys.path.insert(0, os.path.abspath(BACKEND_DIR))
os.environ.setdefault("MODEL_CACHE_DIR", os.path.expanduser("~/.amtza/models"))

import numpy as np  # noqa: E402

from embeddings import (  # noqa: E402
    WordNotFoundError,
    _is_good_idx,
    _phrase_tokens,
    compute_midpoint,
    find_best_middle,
    get_word_vector,
    load_or_download_sync,
    normalize_word,
    phrase_vec,
)
from game import check_win, _effective_threshold  # noqa: E402

_SPACES = {}


def space_for(lang):
    if lang not in _SPACES:
        print(f"loading {lang} ...")
        _SPACES[lang] = load_or_download_sync(lang)
    return _SPACES[lang]


def candidates(space, w1, w2, exclude=frozenset(), k=12):
    """Top-k good middle-word candidates near the midpoint, with min-sim scores."""
    v1 = phrase_vec(space, w1)
    v2 = phrase_vec(space, w2)
    mid = compute_midpoint(space, w1, w2)
    n = min(600, len(space.words))
    _, idxs = space.nn_index.kneighbors([mid], n_neighbors=n)
    out = []
    for idx in idxs[0]:
        word = space.words[idx]
        if word in exclude or not _is_good_idx(space, idx):
            continue
        wv = space.matrix[idx]
        s1 = float(np.dot(wv, v1))
        s2 = float(np.dot(wv, v2))
        out.append((word, min(s1, s2), s1, s2))
        if len(out) >= k:
            break
    return out


def inspect(lang, w1, w2):
    space = space_for(lang)
    print(f"\n=== inspect {w1} + {w2} ({lang}) ===")
    pick = find_best_middle(space, w1, w2, exclude=_phrase_tokens(space, w1) | _phrase_tokens(space, w2))
    print(f"computer picks: {pick}")
    print("candidate pool (word | min-sim | sim_w1 | sim_w2):")
    for word, mn, s1, s2 in candidates(space, w1, w2):
        star = "  <-- pick" if word == pick else ""
        print(f"  {word:<16} {mn:5.2f}   {s1:5.2f}  {s2:5.2f}{star}")


def play(lang, start1, start2, my_guesses):
    space = space_for(lang)
    used = set(_phrase_tokens(space, start1) | _phrase_tokens(space, start2))
    w1, w2 = start1, start2
    print(f"\n=== play {start1} + {start2} ({lang}) ===")
    for rnd in range(1, 40):
        exclude = set(used)
        try:
            comp = find_best_middle(space, w1, w2, exclude=exclude)
        except WordNotFoundError as e:
            print(f"round {rnd}: word not found: {e}")
            return
        if comp is None:
            print(f"round {rnd}: computer found no middle word (exclude set too large)")
            return

        mine = my_guesses[rnd - 1] if rnd - 1 < len(my_guesses) else None
        if mine is None:
            # Out of my guesses — show the state and candidate pool, then stop.
            print(f"\nround {rnd}: pair = ({w1}, {w2})")
            print(f"  computer would pick: {comp}")
            print("  your move — candidates:")
            for word, mn, s1, s2 in candidates(space, w1, w2, exclude=exclude, k=10):
                print(f"    {word:<16} {mn:5.2f}   {s1:5.2f}  {s2:5.2f}")
            return

        cv = get_word_vector(space, comp)
        try:
            pv = phrase_vec(space, normalize_word(mine, lang))
        except WordNotFoundError:
            print(f"round {rnd}: YOUR word '{mine}' is not in vocab — pick another.")
            return
        sim = float(np.dot(pv, cv))
        won = check_win(mine, comp, pv, cv, rnd)
        bar = _effective_threshold(rnd)
        print(f"round {rnd:>2}: you={mine:<14} computer={comp:<14} sim={sim:4.2f} bar={bar:4.2f}"
              f"{'   *** WIN ***' if won else ''}")
        if won:
            print(f"\nConverged in {rnd} rounds on ~({mine} / {comp}).")
            return
        used.add(normalize_word(mine, lang))
        used.add(normalize_word(comp, lang))
        w1, w2 = mine, comp
    print("… 39 rounds, no convergence.")


def survey(lang):
    """Inspect the computer's middle-word pick for every starting pair + a few
    hand-picked probe pairs, to judge overall word quality in one model load."""
    from word_pairs import STARTING_PAIRS
    space = space_for(lang)
    pairs = [(p["word1"], p["word2"]) for p in STARTING_PAIRS if p["language"] == lang]
    probes = {
        "he": [("שמח", "עצוב"), ("מלך", "מלכה"), ("חתונה", "גירושין"),
               ("תפוח", "עץ"), ("מורה", "תלמיד"), ("שמים", "ארץ")],
        "en": [("happy", "sad"), ("teacher", "student"), ("bread", "butter"),
               ("doctor", "nurse"), ("apple", "tree"), ("summer", "winter")],
    }.get(lang, [])
    print(f"\n########## SURVEY {lang}: computer's middle pick per pair ##########")
    for w1, w2 in pairs + probes:
        try:
            excl = _phrase_tokens(space, w1) | _phrase_tokens(space, w2)
            pick = find_best_middle(space, w1, w2, exclude=excl)
            pool = candidates(space, w1, w2, exclude=excl, k=6)
            pool_str = ", ".join(f"{w}({mn:.2f})" for w, mn, _, _ in pool)
            print(f"  {w1:>10} + {w2:<10} -> {str(pick):<16} | pool: {pool_str}")
        except WordNotFoundError as e:
            print(f"  {w1:>10} + {w2:<10} -> ERROR: {e}")


if __name__ == "__main__":
    args = sys.argv[1:]
    mode = args[0]
    if mode == "inspect":
        inspect(args[1], args[2], args[3])
    elif mode == "survey":
        survey(args[1])
    elif mode == "pairs":
        # playtest.py pairs he  w1 w2  w1 w2 ...  — audition candidate pairs.
        lang = args[1]
        space = space_for(lang)
        rest = args[2:]
        for i in range(0, len(rest) - 1, 2):
            w1, w2 = rest[i], rest[i + 1]
            try:
                excl = _phrase_tokens(space, w1) | _phrase_tokens(space, w2)
                pick = find_best_middle(space, w1, w2, exclude=excl)
                pool = candidates(space, w1, w2, exclude=excl, k=6)
                pool_str = ", ".join(f"{w}({mn:.2f})" for w, mn, _, _ in pool)
                print(f"  {w1:>10} + {w2:<10} -> {str(pick):<16} | {pool_str}")
            except WordNotFoundError as e:
                print(f"  {w1:>10} + {w2:<10} -> ERROR: {e}")
    elif mode == "play":
        sep = args.index("--") if "--" in args else len(args)
        lang, s1, s2 = args[1], args[2], args[3]
        guesses = args[sep + 1:] if sep < len(args) else []
        play(lang, s1, s2, guesses)
