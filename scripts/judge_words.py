"""Screen candidate words for the playable lists with Claude as the judge.

WHY THIS EXISTS. The lists in backend/data are hand-reviewed, and hand review is
the bottleneck: the Hebrew candidate pool was 4,422 words and reviewing it by eye
is hours of work that has to be redone every time the vocabulary is regenerated.
The rules being applied are mechanical enough to delegate ("is this a real
everyday word in dictionary form, or an inflected form / proper noun / jargon?")
and too semantic for a regex — which is exactly the shape of job a model does
well.

DO NOT TRUST IT BLIND. Run `agree` first. It replays the judge over words that
were already labelled by hand and reports how often the two agree, plus the
disagreements themselves. A high number means the rubric is understood and the
judge can be turned loose; a low number usually means the *rubric* is ambiguous,
not that the model is wrong, and the fix is to sharpen the prompt and re-measure.
Reading the disagreements is the point of the exercise — they are where the
rule you thought you had written differs from the one you actually wrote.

COST. Haiku is used deliberately: this is high-volume classification, the
cheapest current model handles it, and the words go up in batches of 100 so the
rubric is paid for once per batch rather than once per word. At Haiku 4.5's
$1/$5 per MTok, a 4,000-word Hebrew pass is a few cents. Add --batch to halve it
via the Batch API if you are screening tens of thousands.

    export ANTHROPIC_API_KEY=sk-ant-...        # or: ant auth login
    python scripts/judge_words.py agree --lang he --labelled reviewed.tsv
    python scripts/judge_words.py judge --lang he --in cand.txt --out kept.txt

Needs Python >= 3.10 and `pip install anthropic` — deliberately NOT added to
backend/requirements.txt, because nothing in the running game calls it.
"""
import argparse
import json
import sys

MODEL = "claude-haiku-4-5"
BATCH = 100

RUBRIC = """You are screening candidate words for a word game's answer pool.

The game shows a player two words and both sides try to name the word "in the
middle". The computer may only answer with words from this pool, so every word
here is something a player could be shown as an answer and think "yes, fair".

KEEP a word only if ALL of these hold:
- It is a real, current, everyday word an ordinary adult uses or recognises.
- It is in dictionary form: singular, no prefixes, no possessive or construct
  endings, not an inflected verb form or participle.
- It is a common noun or a common adjective.
- It is unambiguous enough to stand alone on screen with no context.

REJECT if ANY of these hold:
- A proper noun: a person, place, brand, organisation, or title. In Hebrew there
  is no capital letter to give these away, so judge by meaning.
- An inflected form: plural, construct, possessive, prefixed (ב/ל/מ/ה/ו/ש/כ in
  Hebrew), or a verb form including infinitives and participles.
- A function word, pronoun, preposition, number, or particle.
- Corpus debris: encyclopedia scaffolding, markup, abbreviations, acronyms,
  transliterated fragments, or web and UI jargon.
- Technical, bureaucratic or academic jargon a child would not recognise.
- A word whose most common reading is a different part of speech than the noun
  you have in mind. If it reads ambiguously, reject it.

Answer for EVERY word given, in the same order."""

SCHEMA = {
    "type": "object",
    "properties": {
        "verdicts": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "word": {"type": "string"},
                    "keep": {"type": "boolean"},
                    "reason": {
                        "type": "string",
                        "enum": ["ok", "proper_noun", "inflected", "function_word",
                                 "corpus_debris", "jargon", "ambiguous"],
                    },
                },
                "required": ["word", "keep", "reason"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["verdicts"],
    "additionalProperties": False,
}


def client():
    try:
        from anthropic import Anthropic
    except ImportError:
        sys.exit("pip install anthropic  (needs Python >= 3.10)")
    # Zero-arg on purpose: it picks up ANTHROPIC_API_KEY, or an `ant auth login`
    # profile, without either being named here.
    return Anthropic()


def judge_batch(cli, lang, words):
    language = "Hebrew" if lang == "he" else "English"
    resp = cli.messages.create(
        model=MODEL,
        max_tokens=8000,
        system=RUBRIC,
        output_config={"format": {"type": "json_schema", "schema": SCHEMA}},
        messages=[{"role": "user",
                   "content": f"Language: {language}\nWords:\n" + "\n".join(words)}],
    )
    text = "".join(b.text for b in resp.content if b.type == "text")
    by_word = {v["word"]: v for v in json.loads(text)["verdicts"]}
    # Never silently drop a word the judge skipped: an omission is a reject that
    # nobody decided, which is the one failure mode that quietly shrinks a pool.
    return [by_word.get(w, {"word": w, "keep": False, "reason": "ambiguous"}) for w in words]


def chunks(xs, n):
    for i in range(0, len(xs), n):
        yield xs[i:i + n]


def load_words(path):
    out = []
    for line in open(path, encoding="utf-8"):
        w = line.split("#", 1)[0].strip()
        if w and " " not in w:
            out.append(w)
    return out


def cmd_judge(args):
    cli = client()
    words = load_words(args.infile)
    kept, rejected = [], []
    for i, batch in enumerate(chunks(words, BATCH), 1):
        for v in judge_batch(cli, args.lang, batch):
            (kept if v["keep"] else rejected).append(v)
        print(f"  batch {i}: {len(kept)} kept / {len(kept) + len(rejected)} seen", flush=True)
    with open(args.out, "w", encoding="utf-8") as f:
        f.write("\n".join(v["word"] for v in kept) + "\n")
    print(f"\nkept {len(kept)} of {len(words)} -> {args.out}")
    from collections import Counter
    print("reject reasons:", dict(Counter(v["reason"] for v in rejected)))


def cmd_agree(args):
    """Replay the judge over hand-labelled words and report agreement."""
    cli = client()
    labelled = []
    for line in open(args.labelled, encoding="utf-8"):
        parts = line.rstrip("\n").split("\t")
        if len(parts) == 2 and parts[1] in ("keep", "reject"):
            labelled.append((parts[0], parts[1] == "keep"))
    if not labelled:
        sys.exit("labelled file must be: word<TAB>keep|reject")
    if args.sample and args.sample < len(labelled):
        import random
        labelled = random.Random(0).sample(labelled, args.sample)

    words = [w for w, _ in labelled]
    truth = dict(labelled)
    agree, disagree = 0, []
    for batch in chunks(words, BATCH):
        for v in judge_batch(cli, args.lang, batch):
            if v["keep"] == truth[v["word"]]:
                agree += 1
            else:
                disagree.append((v["word"], truth[v["word"]], v["keep"], v["reason"]))
    n = len(words)
    print(f"\nagreement {agree}/{n} = {100 * agree / n:.1f}%")
    # Both directions, separately: a judge that keeps everything and a judge that
    # rejects everything can share an agreement rate and are not the same problem.
    fp = [d for d in disagree if not d[1] and d[2]]
    fn = [d for d in disagree if d[1] and not d[2]]
    print(f"  judge kept what I rejected: {len(fp)}")
    print(f"  judge rejected what I kept: {len(fn)}")
    print("\ndisagreements (word / mine / judge / reason):")
    for w, mine, theirs, reason in disagree[:60]:
        print(f"  {w:<18} mine={'keep' if mine else 'reject':<6} "
              f"judge={'keep' if theirs else 'reject':<6} {reason}")
    if len(disagree) > 60:
        print(f"  ... and {len(disagree) - 60} more")


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    j = sub.add_parser("judge", help="screen a candidate list")
    j.add_argument("--lang", choices=["he", "en"], required=True)
    j.add_argument("--in", dest="infile", required=True)
    j.add_argument("--out", required=True)
    j.set_defaults(fn=cmd_judge)

    a = sub.add_parser("agree", help="check the judge against hand labels FIRST")
    a.add_argument("--lang", choices=["he", "en"], required=True)
    a.add_argument("--labelled", required=True, help="TSV: word<TAB>keep|reject")
    a.add_argument("--sample", type=int, default=200)
    a.set_defaults(fn=cmd_agree)

    args = ap.parse_args()
    args.fn(args)


if __name__ == "__main__":
    main()
