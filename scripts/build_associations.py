"""Merge the per-word association drafts into backend/data/{lang}_associations.tsv.

The drafts (scripts/data/assoc_out_{lang}{0,1}.tsv) were written per playable word,
by a model asked what an ordinary speaker thinks of on hearing it; see
backend/associations.py for why the game needs them. This step keeps them honest:

  * rows only for words the computer may actually say (the playable list),
  * links only to words the embedding model knows, so every link can be scored,
  * no self-links, no multi-word links, no duplicates,

and reports coverage so a missing chunk is noticed rather than silently shipped.

Usage:
    backend/venv/bin/python scripts/build_associations.py
"""
import glob
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend")))
os.environ.setdefault("MODEL_CACHE_DIR", os.path.expanduser("~/.amtza/models"))

from embeddings import load_or_download_sync  # noqa: E402

HERE = os.path.dirname(__file__)
OUT_DIR = os.path.join(HERE, "..", "backend", "data")


# Catch-all words the drafts attach to everything: "person" was linked from 142
# English words, אדם from 124 Hebrew ones. As links they say nothing ("a soldier
# and a policeman are both people"), yet a word linked to everything is linked to
# both sides of every pair, so it won by default: אדם became the answer to
# soldier+policeman, baby+old man and baby+student. Dropped as links only; the
# computer may still say them when the vectors choose them.
#
# Real categories with many members (animal 137, food 147, חיה, רגש) stay: those
# ARE what people answer.
STOP_LINKS = {
    "he": {"אדם", "איש", "תכונה", "מקום", "פעולה", "דבר", "מצב", "חפץ", "סוג", "תהליך"},
    "en": {"person", "people", "place", "thing", "object", "adjective", "action", "quality",
           "state", "kind", "type", "stuff", "process", "part", "group"},
}


def clean(field, word, vocab, stop=frozenset()):
    seen, out = set(), []
    for w in (x.strip().lower() for x in field.split(",")):
        if not w or " " in w or w == word or w in seen or w not in vocab or w in stop:
            continue
        seen.add(w)
        out.append(w)
    return out


def build(lang):
    space = load_or_download_sync(lang)
    vocab = space.word_to_idx
    playable = {space.words[i] for i in space.good_indices}
    rows, dropped_links, kept_links = {}, 0, 0
    for path in sorted(glob.glob(os.path.join(HERE, "data", f"assoc_out_{lang}*.tsv"))):
        with open(path, encoding="utf-8") as f:
            for line in f:
                line = line.rstrip("\n")
                parts = line.split("\t") if "\t" in line else line.split("|")
                if len(parts) < 3:
                    continue
                word = parts[0].strip().lower()
                if word not in playable or word in rows:
                    continue
                stop = STOP_LINKS.get(lang, set())
                cats = clean(parts[1], word, vocab, stop)
                assoc = [a for a in clean(parts[2], word, vocab, stop) if a not in cats]
                raw = len([x for x in (parts[1] + "," + parts[2]).split(",") if x.strip()])
                kept_links += len(cats) + len(assoc)
                dropped_links += max(0, raw - len(cats) - len(assoc))
                rows[word] = (cats, assoc)
    out = os.path.join(OUT_DIR, f"{lang}_associations.tsv")
    with open(out, "w", encoding="utf-8") as f:
        f.write(f"# {lang}: word<TAB>categories<TAB>associations. Built by scripts/build_associations.py;"
                f" see backend/associations.py.\n")
        for word in sorted(rows):
            cats, assoc = rows[word]
            f.write(f"{word}\t{','.join(cats)}\t{','.join(assoc)}\n")
    print(f"{lang}: {len(rows):,}/{len(playable):,} playable words covered, "
          f"{kept_links:,} links kept, {dropped_links:,} dropped (unknown word / duplicate / self)")
    missing = sorted(playable - set(rows))
    if missing:
        print(f"  uncovered sample: {', '.join(missing[:15])}")


if __name__ == "__main__":
    for lang in (sys.argv[1:] or ["he", "en"]):
        build(lang)
