"""Better vectors for choosing the computer's middle word (Hebrew).

WHY. The game's Hebrew vectors (wiki.he) come from Wikipedia. Measured against
human answers (scripts/eval_human.py), the computer's first-round word was in a
typical speaker's top three 51% of the time, against ~88% for a second person.
Two free sources, combined, pick better middles: fastText trained on web text
(cc.he.300) and a Hebrew BERT sentence model (AlephBERT). Neither beat wiki.he on
its own; averaged, with the association map on top, on the 313 labelled pairs:

                              wiki.he     cc + AlephBERT
    starting pairs              51%           57%
    mid-game, clear answers     19%           38%
    same word as person B*      21%           26%

    * an independent second labeller whose answers were never used for tuning.

WHAT IT IS. data/he_middle.npz (built by scripts/build_middle_vectors.py): int8
vectors for the 60k most common words, every playable word and the geresh
loanwords. The server never runs either model; it only reads the file.

WHAT IT IS NOT. It only chooses the computer's word. Validating words, deciding
a win, the closeness bar and the hints' neighbourhood all still use wiki.he, so
none of those change. When a word on the board isn't in the table (~1% of what
players type), find_best_middle uses the old path for that round.
"""
import logging
from pathlib import Path

import numpy as np

logger = logging.getLogger(__name__)

DATA_DIR = Path(__file__).parent / "data"

# Each source's similarities are standardised per query (z-scores over the
# playable words), since the two models measure "close" on different scales,
# then averaged with these weights.
SOURCE_WEIGHTS = (0.5, 0.5)   # (cc, AlephBERT)


class MiddleTable:
    def __init__(self, words, cc, aleph):
        self.words = words
        self.index = {w: i for i, w in enumerate(words)}
        self.cc = cc          # int8 (N, 300)
        self.aleph = aleph    # int8 (N, 128)
        self._pool = {}       # id(space) -> (rows_ok, cc_rows, aleph_rows)

    def _row(self, token):
        i = self.index.get(token)
        if i is None:
            # Phones type the geresh as ' or ’ as often as ׳; the table uses '.
            plain = token.replace("׳", "'").replace("’", "'")
            i = self.index.get(plain)
            if i is None and plain.endswith("'") and len(plain) > 2:
                i = self.index.get(plain[:-1])   # trailing geresh: see lookup_index
        return i

    def query(self, phrase: str):
        """(cc, aleph) unit vectors for a phrase, or None if any token is missing."""
        rows = [self._row(t) for t in phrase.split()]
        if not rows or any(r is None for r in rows):
            return None
        out = []
        for m in (self.cc, self.aleph):
            v = m[rows].astype(np.float32).mean(axis=0)
            n = np.linalg.norm(v)
            out.append(v / n if n else v)
        return out

    def pool(self, space):
        """Float32 rows for the space's playable words, aligned with good_indices."""
        key = id(space)
        if key not in self._pool:
            rows = np.array([self.index.get(space.words[i], -1) for i in space.good_indices])
            ok = rows >= 0
            safe = np.where(ok, rows, 0)

            def unit(m):
                x = m[safe].astype(np.float32)
                return x / np.linalg.norm(x, axis=1, keepdims=True).clip(min=1e-9)
            self._pool[key] = (ok, unit(self.cc), unit(self.aleph))
            if not ok.all():
                logger.info(f"middle table: {int((~ok).sum())} playable words without a row")
        return self._pool[key]

    def combined_z(self, space, q):
        """Standardised, source-averaged similarity of every playable word to q."""
        ok, pcc, pal = self.pool(space)
        total = np.zeros(len(ok), dtype=np.float64)
        for weight, rows, vec in zip(SOURCE_WEIGHTS, (pcc, pal), q):
            s = (rows @ vec).astype(np.float64)
            mu, sd = s[ok].mean(), s[ok].std() + 1e-9
            total += weight * (s - mu) / sd
        total[~ok] = -np.inf
        return total


_cache: dict = {}


def load(lang: str) -> "MiddleTable | None":
    if lang in _cache:
        return _cache[lang]
    path = DATA_DIR / f"{lang}_middle.npz"
    table = None
    if path.exists():
        with np.load(path, allow_pickle=False) as z:
            words = str(z["words"]).split("\n")
            table = MiddleTable(words, z["cc"], z["aleph"])
        logger.info(f"Middle-word vectors for {lang}: {len(table.words):,} words")
    _cache[lang] = table
    return table
