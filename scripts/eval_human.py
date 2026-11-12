"""How often does the computer say what a person would say?

Every other harness in this repo plays the computer against a stand-in player that
picks by cosine, which is the same machinery as the computer, so it measures
convergence without ever asking whether the words are the ones people think of.
This one scores the computer's pick against human answers.

THE LABELS. scripts/data/human_labels.tsv holds, for the 213 starting pairs and 100
random mid-game-style pairs, the three answers a typical native speaker would give,
most likely first. They were written by a model playing the role of an ordinary
player, told to give the most obvious word rather than the cleverest, and never
shown the code or the computer's answers. That makes them a proxy for people, not
a survey; treat the absolute numbers with that in mind and the before/after
differences as the signal.

METRIC. hit@3: the computer's word is one of the three human answers. Reported
separately for starting pairs (the first impression) and mid-game pairs (where
the game actually wanders), per language. "mid-clear" drops the mid-game pairs
labelled low-confidence: over half of them, where people would scatter anyway.

Usage:
    backend/venv/bin/python scripts/eval_human.py
    backend/venv/bin/python scripts/eval_human.py --misses he
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend")))
os.environ.setdefault("MODEL_CACHE_DIR", os.path.expanduser("~/.amtza/models"))

from embeddings import (  # noqa: E402
    WordNotFoundError, _phrase_tokens, find_best_middle, load_or_download_sync, normalize_word,
)
from game import same_word  # noqa: E402

LABELS = os.path.join(os.path.dirname(__file__), "data", "human_labels.tsv")
N_START = 213


def load_labels(path=LABELS):
    rows = []
    with open(path, encoding="utf-8") as f:
        for i, line in enumerate(f):
            p = line.rstrip("\n").split("\t")
            if len(p) < 6:
                continue
            rows.append({"lang": p[0], "w1": p[1], "w2": p[2],
                         "answers": [a.strip() for a in p[3:6] if a.strip()],
                         "clear": (p[6].strip() if len(p) > 6 else "") != "low",
                         "start": i < N_START})
    return rows


def evaluate(rows, pick=find_best_middle, spaces=None):
    spaces = spaces if spaces is not None else {}
    out = {}
    for lang in ("he", "en"):
        if lang not in spaces:
            spaces[lang] = load_or_download_sync(lang)
        space = spaces[lang]
        for split in ("start", "mid", "mid-clear"):
            hits, misses, n = 0, [], 0
            for r in rows:
                if r["lang"] != lang or r["start"] != (split == "start"):
                    continue
                if split == "mid-clear" and not r["clear"]:
                    continue
                try:
                    exclude = _phrase_tokens(space, r["w1"]) | _phrase_tokens(space, r["w2"])
                    word = pick(space, r["w1"], r["w2"], exclude)
                except WordNotFoundError:
                    continue
                n += 1
                answers = [normalize_word(a, lang) for a in r["answers"]]
                if word and any(same_word(word, a) for a in answers):
                    hits += 1
                else:
                    misses.append((r["w1"], r["w2"], word, answers[0] if answers else ""))
            out[(lang, split)] = {"n": n, "hit3": hits / n if n else 0.0, "misses": misses}
    return out


def show(res, label=""):
    cells = " | ".join(f"{lang} {split} {res[(lang, split)]['hit3']:.0%} (n={res[(lang, split)]['n']})"
                       for lang in ("he", "en") for split in ("start", "mid", "mid-clear"))
    print(f"{label:28s} {cells}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--misses", choices=["he", "en"], help="list the misses for one language")
    args = ap.parse_args()
    res = evaluate(load_labels())
    show(res, "production")
    if args.misses:
        for split in ("start", "mid"):
            for w1, w2, got, want in res[(args.misses, split)]["misses"]:
                print(f"  [{split}] {w1} + {w2}: computer={got}  human={want}")


if __name__ == "__main__":
    main()
