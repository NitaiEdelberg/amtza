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

REGRESSION GATE (CI). --check compares against scripts/data/eval_baseline.json and
exits non-zero if any split lost more than --tolerance pairs. The tolerance is in
pairs, not percent, because the mid-game splits are small (n=21-50): one pair there
is 2-5 points, and a percentage tolerance would be either deaf on the big splits or
trigger-happy on the small ones. After an intended improvement, refresh the
baseline with --write-baseline and commit it alongside the change that earned it.

Usage:
    backend/venv/bin/python scripts/eval_human.py
    backend/venv/bin/python scripts/eval_human.py --misses he
    backend/venv/bin/python scripts/eval_human.py --check
    backend/venv/bin/python scripts/eval_human.py --write-baseline
"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend")))
os.environ.setdefault("MODEL_CACHE_DIR", os.path.expanduser("~/.amtza/models"))

from embeddings import (  # noqa: E402
    WordNotFoundError, _phrase_tokens, find_best_middle, load_or_download_sync, normalize_word,
)
from game import same_word  # noqa: E402

LABELS = os.path.join(os.path.dirname(__file__), "data", "human_labels.tsv")
BASELINE = os.path.join(os.path.dirname(__file__), "data", "eval_baseline.json")
SPLITS = ("start", "mid", "mid-clear")
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
        for split in SPLITS:
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
            out[(lang, split)] = {"n": n, "hits": hits, "hit3": hits / n if n else 0.0,
                                  "misses": misses}
    return out


def show(res, label=""):
    cells = " | ".join(f"{lang} {split} {res[(lang, split)]['hit3']:.0%} (n={res[(lang, split)]['n']})"
                       for lang in ("he", "en") for split in SPLITS)
    print(f"{label:28s} {cells}")


def check(res, baseline, tolerance):
    """Rows of (name, baseline hits, current hits, n, ok) and whether all passed."""
    rows, ok_all = [], True
    for lang in ("he", "en"):
        for split in SPLITS:
            key = f"{lang}-{split}"
            cur = res[(lang, split)]
            base = baseline.get(key)
            if base is None:
                continue
            if base["n"] != cur["n"]:
                # The labels or pairs changed; comparing counts would be meaningless.
                rows.append((key, base["hits"], cur["hits"], cur["n"], False))
                ok_all = False
                continue
            ok = cur["hits"] >= base["hits"] - tolerance
            ok_all &= ok
            rows.append((key, base["hits"], cur["hits"], cur["n"], ok))
    return rows, ok_all


def summary_markdown(rows, tolerance):
    lines = ["### Human-match eval (computer's word among a typical speaker's top 3)", "",
             "| split | baseline | now | n | |", "|---|---|---|---|---|"]
    for key, base, cur, n, ok in rows:
        lines.append(f"| {key} | {base} ({base / n:.0%}) | {cur} ({cur / n:.0%}) | {n} | "
                     f"{'✅' if ok else '❌'} |")
    lines.append("")
    lines.append(f"Fails when a split loses more than {tolerance} pairs against "
                 f"`scripts/data/eval_baseline.json`.")
    return "\n".join(lines) + "\n"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--misses", choices=["he", "en"], help="list the misses for one language")
    ap.add_argument("--check", action="store_true", help="fail on regression against the baseline")
    ap.add_argument("--tolerance", type=int, default=2, help="pairs a split may lose (default 2)")
    ap.add_argument("--write-baseline", action="store_true", help="record current results as baseline")
    args = ap.parse_args()
    res = evaluate(load_labels())
    show(res, "production")
    if args.write_baseline:
        data = {f"{lang}-{split}": {"hits": res[(lang, split)]["hits"], "n": res[(lang, split)]["n"]}
                for lang in ("he", "en") for split in SPLITS}
        with open(BASELINE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
            f.write("\n")
        print(f"wrote {BASELINE}")
    if args.check:
        with open(BASELINE, encoding="utf-8") as f:
            baseline = json.load(f)
        rows, ok = check(res, baseline, args.tolerance)
        md = summary_markdown(rows, args.tolerance)
        print(md)
        if os.getenv("GITHUB_STEP_SUMMARY"):
            with open(os.environ["GITHUB_STEP_SUMMARY"], "a", encoding="utf-8") as f:
                f.write(md)
        if not ok:
            sys.exit(1)
    if args.misses:
        for split in ("start", "mid"):
            for w1, w2, got, want in res[(args.misses, split)]["misses"]:
                print(f"  [{split}] {w1} + {w2}: computer={got}  human={want}")


if __name__ == "__main__":
    main()
