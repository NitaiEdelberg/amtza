"""Play real games with a human (or a model) supplying the guesses.

Why this exists: every convergence number in this repo came from a stand-in
player that picks words by cosine — it searches near the midpoint and samples
from the best-scoring candidates. A person does not do that. A person reads
"בית / מרפסת" and thinks "גינה", from meaning, with no idea what the computer's
pool contains. Those two players fail in different places, so a number measured
with one says little about the other.

This harness holds several games open at once and advances them a round at a
time, so a real player can answer for all of them in one pass instead of
round-tripping each game separately.

    python scripts/play_session.py init  --lang he --games 6
    python scripts/play_session.py step  --guess גינה --guess ערב ...
    python scripts/play_session.py report

Game logic is imported, never reimplemented: the same find_best_middle,
check_win and homing curve the server runs. If this file disagrees with the
game, it is this file that is wrong.
"""
import argparse
import json
import os
import random
import statistics
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend")))
os.environ.setdefault("MODEL_CACHE_DIR", os.path.expanduser("~/.amtza/models"))
os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")

import logging  # noqa: E402
logging.disable(logging.INFO)

import numpy as np  # noqa: E402
from embeddings import (  # noqa: E402
    WordNotFoundError, _phrase_tokens, find_best_middle, get_word_vector,
    load_or_download_sync, normalize_word, phrase_vec,
)
from game import check_win, _effective_threshold  # noqa: E402
from word_pairs import STARTING_PAIRS  # noqa: E402

STATE = os.path.join(os.path.dirname(__file__), ".play_session.json")
MAX_ROUNDS = 30
_SPACES = {}


def space(lang):
    if lang not in _SPACES:
        _SPACES[lang] = load_or_download_sync(lang)
    return _SPACES[lang]


def load():
    with open(STATE, encoding="utf-8") as f:
        return json.load(f)


def save(s):
    with open(STATE, "w", encoding="utf-8") as f:
        json.dump(s, f, ensure_ascii=False, indent=1)


def cmd_init(a):
    rng = random.Random(a.seed)
    pairs = [p for p in STARTING_PAIRS if p["language"] == a.lang]
    chosen = rng.sample(pairs, min(a.games, len(pairs)))
    s = {"lang": a.lang, "games": [
        {"id": i + 1, "w1": p["word1"], "w2": p["word2"],
         "start": [p["word1"], p["word2"]],
         "used": sorted(_phrase_tokens(space(a.lang), p["word1"]) |
                        _phrase_tokens(space(a.lang), p["word2"])),
         "round": 1, "status": "active", "history": []}
        for i, p in enumerate(chosen)]}
    save(s)
    show(s)


def show(s):
    active = [g for g in s["games"] if g["status"] == "active"]
    print(f"\n=== {s['lang']}  ({len(active)} active, "
          f"{sum(1 for g in s['games'] if g['status'] == 'won')} won, "
          f"{sum(1 for g in s['games'] if g['status'] == 'gave_up')} gave up) ===")
    for g in active:
        bar = _effective_threshold(g["round"])
        print(f"  game {g['id']}  round {g['round']:>2}  bar {bar:.0%}   "
              f"{g['w1']}  ↔  {g['w2']}")
    if active:
        print(f"\n  supply {len(active)} guesses, in game-id order: "
              f"{', '.join(str(g['id']) for g in active)}")


def cmd_step(a):
    s = load()
    lang = s["lang"]
    sp = space(lang)
    active = [g for g in s["games"] if g["status"] == "active"]
    if len(a.guess) != len(active):
        sys.exit(f"got {len(a.guess)} guesses for {len(active)} active games")

    for g, guess in zip(active, a.guess):
        try:
            pv = phrase_vec(sp, normalize_word(guess, lang))
        except WordNotFoundError:
            print(f"  game {g['id']}: '{guess}' is not in the vocabulary — "
                  f"guess again for this one (round unchanged)")
            continue
        used = set(g["used"])
        comp = find_best_middle(sp, g["w1"], g["w2"], exclude=used)
        if comp is None:
            g["status"] = "gave_up"
            continue
        cv = get_word_vector(sp, comp)
        sim = float(np.dot(pv, cv))
        won = check_win(guess, comp, pv, cv, g["round"])
        g["history"].append({"round": g["round"], "you": guess,
                             "computer": comp, "sim": round(sim, 3)})
        print(f"  game {g['id']} r{g['round']:>2}: you={guess:<12} "
              f"computer={comp:<14} {sim:.0%}"
              f"{'   *** WIN ***' if won else ''}")
        if won:
            g["status"] = "won"
            continue
        used |= {normalize_word(guess, lang), normalize_word(comp, lang)}
        g["used"] = sorted(used)
        g["w1"], g["w2"] = guess, comp
        g["round"] += 1
        if g["round"] > MAX_ROUNDS:
            g["status"] = "gave_up"
    save(s)
    show(s)


def cmd_report(a):
    s = load()
    won = [g for g in s["games"] if g["status"] == "won"]
    rounds = [g["history"][-1]["round"] for g in won]
    n = len(s["games"])
    print(f"\n=== {s['lang']}: {n} games played by hand ===")
    print(f"  converged: {len(won)}/{n} ({100*len(won)/n:.0f}%)")
    if rounds:
        print(f"  rounds: median {statistics.median(rounds):.1f}  "
              f"mean {statistics.mean(rounds):.1f}  min {min(rounds)}  max {max(rounds)}")
    for g in s["games"]:
        last = g["history"][-1] if g["history"] else None
        tail = (f"{last['you']}/{last['computer']} {last['sim']:.0%}" if last else "-")
        print(f"    game {g['id']}: {g['start'][0]}+{g['start'][1]:<10} "
              f"{g['status']:<8} {len(g['history']):>2} rounds   {tail}")


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    i = sub.add_parser("init"); i.add_argument("--lang", choices=["he", "en"], required=True)
    i.add_argument("--games", type=int, default=6); i.add_argument("--seed", type=int, default=1)
    i.set_defaults(fn=cmd_init)
    st = sub.add_parser("step"); st.add_argument("--guess", action="append", default=[])
    st.set_defaults(fn=cmd_step)
    r = sub.add_parser("report"); r.set_defaults(fn=cmd_report)
    a = ap.parse_args(); a.fn(a)


if __name__ == "__main__":
    main()
