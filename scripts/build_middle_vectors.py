"""Build backend/data/he_middle.npz, the vectors the computer picks Hebrew middles with.

WHY. The game's Hebrew vectors (wiki.he) were trained on Wikipedia, and the
computer's first-round answer matched a typical speaker's top three only ~51% of
the time (two people: ~88%). Measured on scripts/data/human_labels.tsv, two free
sources picked better middles together than the old vectors could with any
tuning:

  * cc.he.300 - fastText trained on web text (Common Crawl), not an encyclopedia.
  * imvladikon/sentence-transformers-alephbert - a Hebrew BERT sentence model.

Neither beat wiki.he alone on starting pairs; averaged (each standardised per
query) they did. See backend/middle_vectors.py for how they are used and the
measurements.

WHAT IS STORED. One row per word: the 60,000 most frequent words of the game's
own vocabulary (which cover ~99% of the Hebrew words play-testers typed), every
playable word, and the geresh loanwords. Columns: cc (300 dims) and AlephBERT
reduced to 128 dims with PCA, each L2-normalised and stored as int8 (x127).
About 25MB; quantising measured as free, PCA of AlephBERT 768->128 cost nothing
beyond noise.

The server never runs either model: it only reads this file.

Run on a dev machine (needs ~3GB disk for the .bin, a few minutes):
    python -m venv ~/.cache/amtza-ml
    ~/.cache/amtza-ml/bin/pip install torch==2.4.1 --index-url https://download.pytorch.org/whl/cpu
    ~/.cache/amtza-ml/bin/pip install transformers==4.46.3 sentence-transformers==3.2.1 "numpy<1.25"
    curl -L -o cc.he.300.bin https://huggingface.co/facebook/fasttext-he-vectors/resolve/main/model.bin
    ~/.cache/amtza-ml/bin/python scripts/build_middle_vectors.py --bin cc.he.300.bin
"""
import argparse
import json
import os
import pickle
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / "backend"))

from fasttext_bin import read_model, word_vector  # noqa: E402

ALEPHBERT = "imvladikon/sentence-transformers-alephbert"
ALEPH_DIMS = 128
HE_CHARS = set("אבגדהוזחטיכלמנסעפצקרשתךםןףץ'׳")


def playable_words():
    out = []
    for line in (HERE.parent / "backend" / "data" / "he_playable.txt").read_text(encoding="utf-8").splitlines():
        w = line.split("#", 1)[0].strip()
        if w and " " not in w:
            out.append(w)
    return out


def table_words(vocab, top):
    from embeddings import _HE_GERESH_ALIASES  # noqa: E402
    words, seen = [], set()
    for w in list(vocab[:top]) + playable_words() + list(_HE_GERESH_ALIASES):
        if w not in seen and w and all(c in HE_CHARS for c in w):
            seen.add(w)
            words.append(w)
    return words


def int8_rows(m):
    m = m / np.linalg.norm(m, axis=1, keepdims=True).clip(min=1e-9)
    return np.round(m * 127).astype(np.int8)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--bin", required=True, help="cc.he.300.bin")
    ap.add_argument("--vocab", default=os.path.expanduser("~/.amtza/models/he_v4_words.pkl"),
                    help="the game's Hebrew vocabulary, frequency order")
    ap.add_argument("--top", type=int, default=60000)
    ap.add_argument("--out", default=str(HERE.parent / "backend" / "data" / "he_middle.npz"))
    args = ap.parse_args()

    vocab = pickle.load(open(args.vocab, "rb"))
    words = table_words(vocab, args.top)
    print(f"{len(words):,} words", flush=True)

    model = read_model(args.bin)
    vecs = [word_vector(model, w) for w in words]
    # Short words the web model never saw have no n-grams to rebuild them from;
    # they are left out and fall back to the old vectors at runtime.
    dropped = [w for w, v in zip(words, vecs) if v is None]
    words = [w for w, v in zip(words, vecs) if v is not None]
    cc = np.stack([v for v in vecs if v is not None]).astype(np.float32)
    print(f"cc vectors done ({len(dropped)} without one: {', '.join(dropped[:12])})", flush=True)

    from sentence_transformers import SentenceTransformer
    st = SentenceTransformer(ALEPHBERT, device="cpu")
    aleph = st.encode(words, batch_size=256, normalize_embeddings=True, show_progress_bar=False)
    centred = aleph - aleph.mean(axis=0)
    _, _, vt = np.linalg.svd(centred[:: max(1, len(words) // 20000)], full_matrices=False)
    aleph = centred @ vt[:ALEPH_DIMS].T
    print("alephbert vectors done", flush=True)

    meta = {"sources": ["cc.he.300 (fastText, Common Crawl)", f"{ALEPHBERT} PCA-{ALEPH_DIMS}"],
            "rows": len(words), "top": args.top}
    np.savez_compressed(args.out, words=np.array("\n".join(words)), cc=int8_rows(cc),
                        aleph=int8_rows(aleph), meta=np.array(json.dumps(meta)))
    print(f"wrote {args.out} ({os.path.getsize(args.out) / 1e6:.1f}MB)")


if __name__ == "__main__":
    main()
