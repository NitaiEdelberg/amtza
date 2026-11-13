"""What people think of when they hear a word, for the words the computer may say.

WHY THIS EXISTS. Word vectors know which words appear near each other in text,
which is not the same as what a person reaches for. Asked for the middle of
apple and tree, people say "fruit"; the vectors rank fig, olive and plum above it,
because the members of a category sit closer to each other than to the category's
name. Holiday + candles is "Hanukkah" to every Israeli and "custom" to the vectors.
A play-test and a 313-pair human benchmark (scripts/eval_human.py) both found that
this, not the similarity maths, is why the computer's middles feel off.

WHAT IT IS. data/{lang}_associations.tsv, one row per playable word:
    word <TAB> categories <TAB> associations
Categories are the broader words it belongs to (תפוח -> פרי), associations the
words people say first on hearing it (נר -> חנוכה, אש, אור…), strongest first.
Written per word, never per pair, so nothing in it was fitted to the benchmark.

A link between a candidate and a word on the board counts in either direction:
the candidate's list mentions the word, or the word's own list mentions the
candidate. The second matters because the player's word can be anything in the
150k vocabulary, while only playable words have rows.
"""
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

DATA_DIR = Path(__file__).parent / "data"

_HE_FINAL_TO_REGULAR = {"ך": "כ", "ם": "מ", "ן": "נ", "ף": "פ", "ץ": "צ"}


# Link strengths: categories at CATEGORY or above, associations below it.
CATEGORY = 0.9


def _weights(categories, associations):
    """Strength per linked word: categories strongest, associations by rank."""
    out = {}
    for i, w in enumerate(categories):
        out.setdefault(w, 1.0 if i == 0 else CATEGORY)
    for i, w in enumerate(associations):
        out.setdefault(w, max(0.5, 0.85 - 0.05 * i))
    return out


def _lookup_keys(word: str, lang: str) -> list:
    """The word plus its singular / article-less forms, to find a row."""
    w = word.strip().lower()
    keys = [w]
    if lang == "he":
        if w.startswith("ה") and len(w) >= 3:
            keys.append(w[1:])
        for k in list(keys):
            if k.endswith(("ים", "ות")) and len(k) >= 4:
                stem = k[:-2]
                keys += [stem, stem + "ה"]
                fin = {"כ": "ך", "מ": "ם", "נ": "ן", "פ": "ף", "צ": "ץ"}
                if stem and stem[-1] in fin:
                    keys.append(stem[:-1] + fin[stem[-1]])
    else:
        if w.endswith("ies") and len(w) >= 5:
            keys.append(w[:-3] + "y")
        elif w.endswith("es") and len(w) >= 4:
            keys += [w[:-2], w[:-1]]
        elif w.endswith("s") and len(w) >= 4:
            keys.append(w[:-1])
    return keys


class Associations:
    def __init__(self, rows: dict, lang: str):
        self.lang = lang
        self.forward = rows                   # word -> {linked word: weight}
        self.reverse = {}                     # linked word -> {word: weight}
        for word, links in rows.items():
            for other, wt in links.items():
                prev = self.reverse.setdefault(other, {})
                prev[word] = max(prev.get(word, 0.0), wt)

    def __len__(self):
        return len(self.forward)

    def links_of(self, word: str) -> dict:
        """{candidate: strength} for everything linked to `word`, either direction.

        Built once per board word, so scoring ~800 candidates is a dict lookup each
        rather than a re-derivation of the word's forms per candidate, which doubled
        a guess's CPU on the free 0.1-CPU instance.
        """
        out = {}
        for token in word.split():
            for key in _lookup_keys(token, self.lang):
                for table in (self.forward.get(key, {}), self.reverse.get(key, {})):
                    for other, wt in table.items():
                        if wt > out.get(other, 0.0):
                            out[other] = wt
        return out

    def link(self, candidate: str, word: str) -> float:
        """0..1 strength of the everyday connection between the two."""
        return self.links_of(word).get(candidate, 0.0)

    def linked_to(self, word: str) -> set:
        """Every word with any link to `word`, for widening the candidate set."""
        return set(self.links_of(word))


_cache: dict = {}


def load(lang: str) -> "Associations | None":
    """The association map for a language, or None if its file is absent."""
    if lang in _cache:
        return _cache[lang]
    path = DATA_DIR / f"{lang}_associations.tsv"
    result = None
    if path.exists():
        rows = {}
        for line in path.read_text(encoding="utf-8").splitlines():
            parts = line.split("\t")
            if len(parts) < 3 or line.startswith("#"):
                continue
            word = parts[0].strip().lower()
            cats = [c.strip().lower() for c in parts[1].split(",") if c.strip()]
            assoc = [a.strip().lower() for a in parts[2].split(",") if a.strip()]
            # Multi-word entries can't be matched against single tokens.
            cats = [c for c in cats if " " not in c and c != word]
            assoc = [a for a in assoc if " " not in a and a != word]
            rows[word] = _weights(cats, assoc)
        result = Associations(rows, lang)
        logger.info(f"Associations for {lang}: {len(result):,} words")
    _cache[lang] = result
    return result
