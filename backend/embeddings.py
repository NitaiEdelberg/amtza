import os
import gzip
import pickle
import logging
import asyncio
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
from sklearn.neighbors import NearestNeighbors

logger = logging.getLogger(__name__)

CACHE_DIR = Path(os.getenv("MODEL_CACHE_DIR", str(Path.home() / ".amtza" / "models")))

VEC_URLS = {
    "he": "https://dl.fbaipublicfiles.com/fasttext/vectors-wiki/wiki.he.vec",
    "en": "https://dl.fbaipublicfiles.com/fasttext/vectors-crawl/cc.en.300.vec.gz",
}

MAX_WORDS = 150_000


@dataclass
class EmbeddingSpace:
    words: list
    word_to_idx: dict
    matrix: np.ndarray  # shape (N, 300), L2-normalized, float32
    nn_index: NearestNeighbors
    language: str
    noun_proto: "np.ndarray | None" = None  # prototype vector for Hebrew nouns
    verb_proto: "np.ndarray | None" = None  # prototype vector for Hebrew verbs/adjectives
    _contamination_cache: dict = field(default_factory=dict)  # word -> bool, memoized neighbor-purity check
    good_mask: "np.ndarray | None" = None  # bool[N]: whether words[i] passes _is_good_suggestion (precomputed at load)


class WordNotFoundError(Exception):
    pass


def normalize_word(word: str, lang: str) -> str:
    word = word.strip()
    if lang == "he":
        # Strip niqqud (U+05B0–U+05C7), cantillation, makaf, paseq
        word = "".join(
            c for c in word
            if not ("ְ" <= c <= "ׇ")
            and c != "־"
            and c != "׀"
        )
    else:
        word = word.lower()
    return word


def detect_language(word: str) -> str:
    if any("֐" <= c <= "׿" for c in word):
        return "he"
    return "en"


# Hebrew base letters (alef–tav + final forms)
_HE_LETTERS = set("אבגדהוזחטיכלמנסעפצקרשתךםןףץ")

# Sensitive-content guard: this is a casual game meant to be shared with friends and
# family. The "middle word" search has no topical anchor, so an unlucky chain of
# locally-plausible neighbours can wander into sexual/drug/extreme-violence territory
# (observed in playtesting: an English game drifted "...woman→prostitute→policeman→
# prison→gangster→criminal"). No blocklist can be exhaustive, but blocking the
# unambiguous core terms for these topics keeps them from ever being *suggested* —
# even if a player later steers there deliberately, the computer never leads the way.
_HE_SENSITIVE_BLOCKLIST = {
    # sex work / explicit sexual content
    "זונה", "זונות", "זנות", "פורנו", "פורנוגרפיה", "זימה",
    # sexual violence
    "אונס", "אנס", "אנסים", "פדופיל", "פדופיליה",
    # hard drugs
    "קוקאין", "הרואין", "סמים",
}

# Historical/geographical proper nouns + known bad forms
_HE_PROPER_NOUN_BLOCKLIST = {
    # Ancient kingdoms/regions
    "אשור", "ארם", "כנען", "מוקדון", "מסופוטמיה", "קפריסין", "פניציה",
    "בורגונדיה", "ביזנטיון", "קרתגו", "פרגמון",
    # Biblical cities
    "סדום", "עמורה", "יריחו",
    # Scientific units / transliterations that are proper nouns
    "צלזיוס", "פרנהייט", "קלווין",
    # Common Anglo-Saxon/medieval names embedded near royalty words
    "אתלסטאן", "אתלברט", "אתלוולף", "ראדוולד", "אתלרד",
    # Verb conjugation forms (past/passive) that look noun-like in embeddings
    "נכבשה", "נוסדה", "נהרסה", "נלחמה", "הוקמה", "מוגש",
    # Passive participial adjectives (Pu'al pattern מ_ו__ת) the rank filter once caught
    "מאוישת", "מאוישים", "מאוחדת", "מחוזקת", "מחוברת",
    # Possessive/construct forms whose bases are not in vocab
    "הולדתו", "מאכלי", "כיבושה", "עונשין",
    # Construct forms of verbal nouns with double-yod (base not in vocab)
    "שתיית", "אכילת", "שתייה", "הגשת",
    # Adjectives that look noun-like (POS prototype can't distinguish)
    "מתוק", "מריר", "חריף", "מלוח", "חמוץ",
    "שורר", "מישורי", "גבולה",
    # Prefixed-possessive/construct forms whose inner base is not detectable by suffix rules
    "בבימויה", "בכיכובה", "בבימויו", "בכיכובו",
    # Construct-state plurals/forms whose base is not in vocab
    "רביעיית", "שלישיית", "חמישיית",
    # Non-words / morphological fragments
    "רטו",
    # Domain-specific jargon unlikely to be useful game words
    "קומיקאי",
    # Irregular plurals whose singular is not in vocab
    "מאכלים", "משקאות",
    # Foreign loanwords / proper material nouns
    "אלומיניום", "פלסטיק", "סיליקון", "קרמיקה",
    # Hebrew calendar months (proper nouns)
    "ניסן", "אייר", "סיון", "תמוז", "אב", "אלול",
    "תשרי", "חשוון", "כסלו", "טבת", "שבט", "אדר",
    # Israeli cities — these flood suggestions whenever any city appears in the pair.
    # Adding ~50 most common ones; the game should never suggest proper city names.
    # Major cities
    "חיפה", "יפו", "אשדוד", "נתניה", "באר שבע", "בת ים", "רמת גן",
    "בני ברק", "בית שמש", "גבעתיים", "הוד השרון",
    # Greater Tel Aviv region
    "חולון", "לוד", "רמלה", "מודיעין", "רחובות", "יבנה", "ראשון לציון",
    "רעננה", "כפר סבא", "הרצליה", "פתח תקווה", "אור יהודה", "קרית אונו",
    # Center/North
    "חדרה", "נהריה", "עכו", "כרמיאל", "קרית שמונה", "קרית ביאליק",
    "אשקלון", "עפולה", "טבריה", "נצרת", "עילוט", "מגדל",
    "אילת", "צפת", "יוקנעם", "זכרון", "בנימינה",
    # Jerusalem area
    "ירושלים", "מעלה אדומים", "בית שאן", "אריאל",
    # Tel Aviv neighborhoods / streets / landmarks
    "דיזנגוף", "שינקין", "רוטשילד", "אלנבי",
    # Israeli geographic regions (generate city-cluster suggestions)
    "יזרעאל", "השרון", "השפלה", "הגליל", "הגולן", "הנגב",
    "הכרמל", "הערבה",
    # Wikipedia community jargon / Wikipedian-name forms — unambiguous (no everyday meaning),
    # appear with deceptively high frequency ranks because the Hebrew model was trained on
    # raw Wikipedia dumps that include talk/meta pages full of editor discussion.
    "ויקיפד", "ויקיפדים", "ויקיפדית", "ויקיפדי", "ויקיפדיים", "הוויקיפדית", "כוויקיפדית",
    "בירוקרט", "ביורוקרט", "עריכותיך", "עריכותיי", "נחסמתי",
    # Surname clusters spotted in playtesting (Hasidic dynasty names) — not real "middle words"
    "הלברשטאם", "הלברשטאט", "טייטלבוים",
    # Hellenistic-period dynasty/ethnonym adjective forms spotted in playtesting
    "הסלאוקית", "הסלווקית", "הפרתית", "התלמיית",
}

# A handful of unambiguous non-Hebrew-script signals: words containing Latin letters,
# digits, hashtags or other symbols are never legitimate Hebrew "middle word" content —
# in this corpus they almost always indicate a contaminated cluster (usernames, handles,
# wiki signatures). Used to detect whether a *candidate*'s neighbourhood is itself
# contaminated (see _is_neighbor_contaminated).
def _looks_non_hebrew(token: str) -> bool:
    return not all(("א" <= c <= "ת") or c in "ךםןףץ" or c.isspace() for c in token)


def _is_neighbor_contaminated(word: str, space: EmbeddingSpace, k: int = 10, ratio: float = 0.3) -> bool:
    """Detect Wikipedia username/talk-page artifacts generically: real Hebrew words cluster
    with other real Hebrew words, but contaminated tokens (editor handles, signatures,
    community jargon) cluster with each other and with Latin-script/hashtag noise. A word
    whose nearest neighbours are mostly non-Hebrew-script is almost certainly itself such
    an artifact — even when the word itself happens to be spelled in Hebrew letters
    (e.g. קיפודנחש, a username, ranks #2107 and looks like an ordinary noun on the surface).
    Result is memoized per EmbeddingSpace since the vocabulary is fixed at load time.
    """
    cached = space._contamination_cache.get(word)
    if cached is not None:
        return cached
    idx = space.word_to_idx.get(word)
    if idx is None:
        return False
    _, indices = space.nn_index.kneighbors([space.matrix[idx]], n_neighbors=k + 1)
    neighbors = [space.words[i] for i in indices[0] if space.words[i] != word][:k]
    if not neighbors:
        space._contamination_cache[word] = False
        return False
    bad = sum(1 for n in neighbors if _looks_non_hebrew(n))
    result = (bad / len(neighbors)) > ratio
    space._contamination_cache[word] = result
    return result


def _batch_contamination_flags(space: EmbeddingSpace, cand_indices: "np.ndarray",
                               k: int = 10, ratio: float = 0.3, chunk: int = 2000) -> dict:
    """Vectorised equivalent of calling _is_neighbor_contaminated() on each candidate.

    Instead of one k-NN query per word (~1000s of brute-force scans per /guess, the
    original bottleneck), compute the top-(k+1) neighbours for a whole chunk of candidate
    vectors at once via a single BLAS matmul, then derive the same non-Hebrew ratio the
    per-word function would. Returns {idx: bool}. The neighbour selection (exclude self by
    word string, take first k, ratio > 0.3) mirrors _is_neighbor_contaminated exactly so
    the set of contaminated words is unchanged.
    """
    words = space.words
    matrix = space.matrix
    flags: dict = {}
    K = k + 1  # match kneighbors(n_neighbors=k+1)
    for start in range(0, len(cand_indices), chunk):
        ci = cand_indices[start:start + chunk]
        sims = matrix[ci] @ matrix.T  # (c, N) cosine sims (matrix is L2-normalised)
        # top-K by similarity per row (unsorted), then sort those K descending
        top = np.argpartition(-sims, kth=K - 1, axis=1)[:, :K]
        row_sims = np.take_along_axis(sims, top, axis=1)
        order = np.argsort(-row_sims, axis=1)
        top_sorted = np.take_along_axis(top, order, axis=1)  # (c, K) sim-descending
        for r, idx in enumerate(ci):
            word = words[idx]
            neighbors = [words[i] for i in top_sorted[r] if words[i] != word][:k]
            if not neighbors:
                flags[int(idx)] = False
                continue
            bad = sum(1 for n in neighbors if _looks_non_hebrew(n))
            flags[int(idx)] = (bad / len(neighbors)) > ratio
    return flags


def _compute_good_mask(space: EmbeddingSpace) -> "np.ndarray":
    """Precompute, for the whole vocabulary, whether each word passes _is_good_suggestion.

    The expensive part (Hebrew neighbour-contamination) is batched: we first run all the
    cheap per-word checks (skip_contamination=True), and only for the words that survive
    those do we run the vectorised k-NN contamination pass. good = cheap_ok AND
    (not contaminated). Because _is_good_suggestion is a logical AND of independent checks,
    this yields exactly the same accept/reject decision as the original per-word call —
    it only moves WHEN the k-NN runs, not WHICH words pass.
    """
    import time
    n = len(space.words)
    t0 = time.time()
    good = np.zeros(n, dtype=bool)

    if space.language == "he":
        cheap_ok = np.fromiter(
            (_is_good_suggestion(space.words[i], space, skip_contamination=True) for i in range(n)),
            dtype=bool, count=n,
        )
        cand = np.nonzero(cheap_ok)[0]
        logger.info(f"good_mask[he]: {len(cand):,}/{n:,} passed cheap checks; "
                    f"batching contamination k-NN...")
        flags = _batch_contamination_flags(space, cand)
        # Populate the per-word memo so any later _is_good_suggestion call is O(1) too.
        for idx, contaminated in flags.items():
            space._contamination_cache[space.words[idx]] = contaminated
        for idx in cand:
            good[idx] = not flags.get(int(idx), False)
    else:
        # English has no contamination check — all checks are cheap.
        for i in range(n):
            good[i] = _is_good_suggestion(space.words[i], space)

    logger.info(f"good_mask[{space.language}]: {int(good.sum()):,}/{n:,} good words "
                f"(computed in {time.time() - t0:.1f}s)")
    return good


def _load_or_compute_good_mask(space: EmbeddingSpace, lang: str) -> None:
    """Attach space.good_mask, loading the disk cache when present else computing + saving it.

    Keyed to the v3 model version and validated against the current vocab length so a stale
    cache (different vocabulary) is transparently recomputed. Cached file: {lang}_v3_good.npy.
    """
    mask_path = CACHE_DIR / f"{lang}_v3_good.npy"
    if mask_path.exists():
        try:
            mask = np.load(str(mask_path))
            if mask.shape == (len(space.words),) and mask.dtype == bool:
                space.good_mask = mask
                logger.info(f"Loaded cached good_mask for {lang}: "
                            f"{int(mask.sum()):,}/{len(space.words):,} good words")
                return
            logger.warning(f"Cached good_mask for {lang} is stale "
                           f"(shape {mask.shape} vs {len(space.words)}); recomputing")
        except Exception as e:
            logger.warning(f"Failed to load good_mask cache for {lang}: {e}; recomputing")
    mask = _compute_good_mask(space)
    space.good_mask = mask
    try:
        np.save(str(mask_path), mask)
        logger.info(f"Cached good_mask for {lang} -> {mask_path}")
    except Exception as e:
        logger.warning(f"Failed to write good_mask cache for {lang}: {e}")


def _is_good_idx(space: EmbeddingSpace, idx: int) -> bool:
    """O(1) good-word check using the precomputed mask, with a safe fallback."""
    if space.good_mask is not None:
        return bool(space.good_mask[idx])
    return _is_good_suggestion(space.words[idx], space)


_HE_VALID_CHARS = _HE_LETTERS | {
    " ",    # multi-word phrases (אייל גולן, מכבי תל אביב)
    "׳",   # geresh U+05F3 — marks foreign consonants (ג׳חנון, צ׳יפס)
    "'",   # ASCII apostrophe — same role when typed on most keyboards
    "’",  # right single quote — common on mobile
    "-",   # hyphen (בית-ספר, פלא-פון)
}


def is_valid_word(space: EmbeddingSpace, word: str) -> bool:
    """Return True if the word/phrase is usable as a player guess.

    Accepts any single word OR multi-word phrase (e.g. 'אייל גולן', 'מכבי תל אביב',
    'New York') as long as at least one token has an embedding vector. The geresh
    character (׳) is also allowed so that loanwords like ג׳חנון can be typed.
    """
    word = word.strip()
    if not word or len(word) > 50:
        return False
    if space.language == "he":
        canonical = normalize_word(word, "he")
        if not all(c in _HE_VALID_CHARS for c in canonical):
            return False
        # At least one actual Hebrew letter required (rejects space-only or apostrophe-only)
        if not any(c in _HE_LETTERS for c in canonical):
            return False
        # Don't require vocab membership: the Hebrew FastText model has gaps (שלום, ביתר…
        # are absent despite being real words). Spurious ✗ for real words would be more
        # confusing than an error message from /guess when no vector is found.
        return True
    # English: letters, spaces, hyphens, apostrophes — at least one token in vocab
    # (English Common Crawl vocab is broad enough that "not in vocab" reliably means "not a word")
    canonical = word.lower().strip()
    tokens = canonical.split()
    if not tokens:
        return False
    if not all(all(c.isalpha() or c in "-'" for c in t) for t in tokens):
        return False
    return any(t in space.word_to_idx for t in tokens)


_HE_PREFIXES_1 = set("בכלושמה")
_HE_PREFIXES_2 = {"ול", "וב", "וכ", "ומ", "שב", "של", "שמ", "הב", "הכ", "המ", "וה", "לה", "בה"}
_HE_SUFFIXES_1 = set("ו")      # possessive: יהודי → יהודיו
_HE_SUFFIXES_2 = {"יו", "יה"}  # plural possessive: ילד → ילדיו

# When a suffix is stripped, the new last letter may need to become a Hebrew final form.
# e.g. זעמו → strip ו → זעמ (non-final מ) but vocab stores זעם (final ם).
_HE_TO_FINAL = {"כ": "ך", "מ": "ם", "נ": "ן", "פ": "ף", "צ": "ץ"}

# Preposition+pronoun forms that should never be game suggestions
_HE_PREPOSITION_FORMS = {
    "עמה", "עמם", "עמנו", "עמהם", "עמכם", "עמהן",
    "איתה", "איתם", "איתנו", "איתו", "איתכם",
    "עימה", "עימם", "עימנו", "עימו", "עמי",
    "אליה", "אליו", "אליהם", "אלינו", "אליכם",
    "ממנה", "ממנו", "מהם", "מהן", "מהנה",
    # 3-char grammatical particles (prefix+root; exempt from the length-4 prefix filter)
    "ועם", "ובן", "ולא", "שלא", "בכל", "לכל", "מכל", "שכן",
    "וכן", "אבל", "אך", "רק", "גם",
    # Short possessive family forms that slip through length-based suffix filters
    "אמו", "אמה", "אבו", "בנו", "בנם", "בתה", "בתו", "בתם",
    "אחיה", "אחיו", "אחיהם", "דודו", "דודה", "סבה", "סבו",
    "כבן", "כבת", "כאב",
    # 3-char construct possessives (len < 4 bypasses suffix filter)
    "דגי", "בני", "אחי", "חמי", "עיי",
    # Construct geographic forms whose bases are not in vocab
    "ימת", "גדת", "גדות", "חציית", "תוואי",
    # Verb infinitives/forms that look noun-like (len < 5 bypasses ל-infinitive filter)
    "לצוד", "לטפס", "לצמוח", "לנוע", "לדוג", "לרוץ",
    # Verb conjugations (Nif'al/past/active) that slip through POS filter
    "נכחד", "נכחדה", "הושמד", "נרצח",
    # Adjectives whose ה-noun base is not in vocab
    "כלכלי", "ביטחוני", "חקלאי",
}


def _with_final(word: str) -> str:
    """Return the word with its last letter converted to final form if applicable."""
    if word and word[-1] in _HE_TO_FINAL:
        return word[:-1] + _HE_TO_FINAL[word[-1]]
    return word


# ── POS prototype seeds ────────────────────────────────────────────────────────
# Used to build noun / verb-adjective prototype vectors at space-build time.
# Suggestions are filtered if their vector is significantly more verb-like than noun-like.
_HE_NOUN_SEEDS = [
    "מלך", "ספר", "בית", "עיר", "כסף", "ים", "הר", "שמש", "כוכב", "ארמון",
    "ילד", "כלב", "דרך", "שיר", "לב", "יד", "עין", "מים", "אש", "רוח",
    "שנה", "יום", "עץ", "פרח", "אריה", "דג", "זהב", "ארץ", "גשר", "ספינה",
    "מדינה", "עם", "שפה", "עבודה", "חלון", "אוניה",
    "נסיך", "כיסא", "ארד", "תלמיד", "אזרח", "מנהיג", "רודן", "אדם",
    "עיתון", "תוכנה", "מחשב", "טלפון", "מכונית", "אנייה", "צבא",
]

_HE_VERB_SEEDS = [
    # past tense (Pa'al, Pi'el, Hif'il, Nif'al)
    "כתב", "ניהל", "ביצע", "הוביל", "הקים", "ייצג", "נולד", "זכה",
    "עמד", "הפך", "גרם", "שיחק", "קיבל", "נתן", "הגיע", "לקח",
    "איחד", "ירש", "תפס", "דיבר", "ניצח", "כבש", "נפל", "פגש",
    "הרג", "נלחם", "ברח", "חזר", "אמר", "ידע", "רצה",
    "נכנס", "יצא", "שלח", "מצא", "ראה", "שמע", "חשב", "קרא",
    # present tense / Pa'al participle (CoCeC pattern)
    "זורם", "נושא", "הולך", "רואה", "שומע", "אוהב", "שונא", "עושה",
    "כותב", "אוכל", "שותה", "ישן", "רץ", "קם", "בא",
    "נוהג", "לוחם", "גדל", "קטן", "נותן", "לוקח", "נסגר", "נפתח",
    "עולה", "יורד", "קופץ", "נופל", "זוכה", "מפסיד", "שולח", "מגיע",
    # hitpa'el / nif'al verb forms
    "התעמת", "התפתח", "התכנס", "נגרם", "נוסד", "התגלה", "נוצר",
]


# Common English adjectives that look noun-like in embeddings (no base in vocab to filter)
# NOTE: keep actual nouns out of here — only pure adjectives with no noun form
# Sensitive-content guard — see _HE_SENSITIVE_BLOCKLIST for rationale. The reported
# English drift ("woman→prostitute→policeman→prison→gangster→criminal") is the
# motivating example: "prostitute" is the unambiguous core term worth gating, while
# the surrounding everyday crime/justice vocabulary (police, prison, criminal…) stays.
_EN_SENSITIVE_BLOCKLIST = {
    # sex work / explicit sexual content
    "prostitute", "prostitutes", "prostitution", "whore", "whores", "slut", "sluts",
    "porn", "porno", "pornography", "brothel", "brothels",
    # sexual violence
    "rape", "rapes", "rapist", "rapists", "molester", "molesters",
    "pedophile", "pedophiles", "paedophile", "paedophiles",
    # hard drugs
    "cocaine", "heroin", "meth", "methamphetamine",
}

_EN_ADJECTIVE_BLOCKLIST = {
    # astronomical adjectives (solar/lunar have no standalone noun form)
    "lunar", "solar", "celestial", "tidal", "orbital",
    "polar", "tropical", "arctic", "volcanic", "seismic",
    # cultural/historical adjectives
    "feudal", "medieval", "archaic", "imperial",
    # political adjectives (use the noun form instead: democracy not democratic)
    "democratic", "autocratic", "authoritarian", "totalitarian",
    # pure adjectives (NOT words that also function as nouns)
    "regal", "sacred", "divine", "mythical", "mystical",
    "spiritual", "magical", "immortal", "eternal", "temporal",
    "earthly", "heavenly",
    # material-state adjectives
    "molten", "frozen", "hollow",
    # common abbreviations that appear in vocabulary
    "gov", "corp", "dept",
}

_EN_NOUN_SEEDS = [
    "king", "book", "city", "gold", "silver", "star", "child", "road",
    "water", "fire", "tree", "flower", "lion", "bridge", "ship", "war",
    "peace", "song", "day", "night", "year", "mountain", "river", "country",
    "cat", "dog", "house", "table", "chair", "sun", "moon", "sky", "ocean",
    "stone", "rock", "bird", "fish", "queen", "prince", "soldier", "teacher",
    "student", "doctor", "artist", "market", "temple", "castle", "village",
    "forest", "desert", "island", "valley", "harbor", "tower", "garden",
]

_EN_NON_NOUN_SEEDS = [
    # past-tense verbs
    "ran", "walked", "wrote", "managed", "won", "led", "fought", "built",
    "created", "destroyed", "fell", "took", "gave", "came", "went", "spoke",
    "heard", "saw", "knew", "loved", "hated", "moved", "started", "ended",
    # present participles / gerunds
    "running", "walking", "writing", "fighting", "building", "creating",
    "moving", "flowing", "rising", "falling", "growing", "shrinking",
    # comparative / superlative adjectives
    "faster", "slower", "bigger", "smaller", "stronger", "weaker",
    "brighter", "darker", "hotter", "colder", "deeper", "shallower",
    "longer", "shorter", "louder", "quieter", "heavier", "lighter",
    # plain descriptive adjectives
    "fast", "slow", "big", "small", "strong", "weak", "bright", "dark",
    "hot", "cold", "deep", "shallow", "long", "short", "loud", "quiet",
    "beautiful", "ugly", "happy", "sad", "good", "bad", "new", "old",
    "quick", "rapid", "ancient", "modern", "heavy", "light",
    # domain-specific adjectives (science/nature/history)
    "lunar", "solar", "stellar", "planetary", "celestial", "cosmic", "orbital",
    "volcanic", "tropical", "arctic", "polar", "oceanic", "tidal",
    "royal", "imperial", "noble", "sacred", "divine", "mortal",
    "historical", "legendary", "mythical", "fictional", "imaginary",
    "distant", "nearby", "central", "outer", "inner", "upper", "lower",
    # adverbs
    "quickly", "slowly", "loudly", "quietly", "deeply", "widely", "broadly",
]


def _build_pos_prototypes(word_to_idx: dict, matrix: np.ndarray, lang: str = "he"):
    """Compute L2-normalised prototype vectors for noun vs non-noun words."""
    noun_seeds = _HE_NOUN_SEEDS if lang == "he" else _EN_NOUN_SEEDS
    non_noun_seeds = _HE_VERB_SEEDS if lang == "he" else _EN_NON_NOUN_SEEDS
    noun_vecs = [matrix[word_to_idx[w]] for w in noun_seeds if w in word_to_idx]
    non_noun_vecs = [matrix[word_to_idx[w]] for w in non_noun_seeds if w in word_to_idx]
    if not noun_vecs or not non_noun_vecs:
        return None, None
    np_arr = np.mean(noun_vecs, axis=0).astype(np.float32)
    vp_arr = np.mean(non_noun_vecs, axis=0).astype(np.float32)
    np_arr /= np.linalg.norm(np_arr)
    vp_arr /= np.linalg.norm(vp_arr)
    return np_arr, vp_arr


def _filter_hebrew_forms(words: list, vectors: list) -> tuple:
    """Remove suffix-possessive Hebrew word forms at load time.
    Prefix forms are filtered at suggestion time (in _is_good_suggestion) to avoid
    removing real root words that share a prefix letter (e.g. שלום would be wrongly
    stripped because ש is a prefix and לום exists in the corpus).
    """
    word_set = set(words)
    kept_words, kept_vecs = [], []
    for word, vec in zip(words, vectors):
        # Suffix possessive ו: זעמו → base זעמ → also check final form זעם
        if len(word) >= 4 and word[-1] in _HE_SUFFIXES_1:
            base = word[:-1]
            if base in word_set or _with_final(base) in word_set:
                continue
        # Suffix possessives יו/יה: ילדיו → base ילדי
        if len(word) >= 5 and word[-2:] in _HE_SUFFIXES_2:
            base = word[:-2]
            if base in word_set or _with_final(base) in word_set:
                continue
        kept_words.append(word)
        kept_vecs.append(vec)
    removed = len(words) - len(kept_words)
    logger.info(f"  Filtered {removed:,} Hebrew suffix-possessive forms, kept {len(kept_words):,} words")
    return kept_words, kept_vecs


def _load_vec_file(path: str, max_words: int = MAX_WORDS, language: str = "en") -> tuple:
    words = []
    vectors = []
    opener = gzip.open if str(path).endswith(".gz") else open
    with opener(path, "rt", encoding="utf-8", errors="ignore") as f:
        first_line = f.readline()  # skip "N dim" header
        logger.info(f"Vec file header: {first_line.strip()}")
        for i, line in enumerate(f):
            if i >= max_words:
                break
            parts = line.rstrip().split(" ")
            if len(parts) < 301:
                continue
            word = parts[0]
            try:
                vec = np.array(parts[1:301], dtype=np.float32)
            except ValueError:
                continue
            if len(vec) != 300:
                continue
            words.append(word)
            vectors.append(vec)
            if i % 10_000 == 0 and i > 0:
                logger.info(f"  Loaded {i:,} words...")
    logger.info(f"Loaded {len(words):,} words total")

    if language == "he":
        words, vectors = _filter_hebrew_forms(words, vectors)

    matrix = np.vstack(vectors).astype(np.float32)
    norms = np.linalg.norm(matrix, axis=1, keepdims=True)
    norms = np.where(norms == 0, 1.0, norms)
    matrix /= norms
    return words, matrix


def _build_space(words: list, matrix: np.ndarray, language: str) -> EmbeddingSpace:
    word_to_idx = {w: i for i, w in enumerate(words)}
    logger.info(f"Building NN index for {language} ({len(words):,} words)...")
    nn = NearestNeighbors(n_neighbors=20, metric="cosine", algorithm="brute")
    nn.fit(matrix)
    logger.info(f"NN index built for {language}")
    noun_proto, verb_proto = _build_pos_prototypes(word_to_idx, matrix, language)
    logger.info(f"POS prototypes built for {language}")
    return EmbeddingSpace(words=words, word_to_idx=word_to_idx, matrix=matrix,
                          nn_index=nn, language=language,
                          noun_proto=noun_proto, verb_proto=verb_proto)


async def _download_file(url: str, dest: Path):
    import urllib.request
    logger.info(f"Downloading {url} -> {dest}")
    dest.parent.mkdir(parents=True, exist_ok=True)
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(None, lambda: urllib.request.urlretrieve(url, str(dest)))
    logger.info(f"Download complete: {dest} ({dest.stat().st_size // 1_048_576}MB)")


def load_or_download_sync(lang: str) -> EmbeddingSpace:
    """Synchronous version for use in run_in_executor."""
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    npy_path = CACHE_DIR / f"{lang}_v3.npy"
    words_path = CACHE_DIR / f"{lang}_v3_words.pkl"
    # older cache paths for migration
    v1_npy = CACHE_DIR / f"{lang}.npy"
    v1_words = CACHE_DIR / f"{lang}_words.pkl"
    v2_npy = CACHE_DIR / f"{lang}_v2.npy"
    v2_words = CACHE_DIR / f"{lang}_v2_words.pkl"

    if npy_path.exists() and words_path.exists():
        logger.info(f"Loading cached {lang} embeddings from {CACHE_DIR}...")
        matrix = np.load(str(npy_path))
        with open(words_path, "rb") as f:
            words = pickle.load(f)
        logger.info(f"Loaded {len(words):,} {lang} words from cache")
    elif (v2_npy.exists() and v2_words.exists()) or (v1_npy.exists() and v1_words.exists()):
        src_npy = v2_npy if v2_npy.exists() else v1_npy
        src_words = v2_words if v2_words.exists() else v1_words
        logger.info(f"Migrating {lang} cache to v3 (applying suffix+prefix filter)...")
        matrix_raw = np.load(str(src_npy))
        with open(src_words, "rb") as f:
            words_raw = pickle.load(f)
        if lang == "he":
            vectors_list = [matrix_raw[i] for i in range(len(words_raw))]
            words, vectors_list = _filter_hebrew_forms(words_raw, vectors_list)
            matrix = np.vstack(vectors_list).astype(np.float32)
            norms = np.linalg.norm(matrix, axis=1, keepdims=True)
            norms = np.where(norms == 0, 1.0, norms)
            matrix /= norms
        else:
            words, matrix = words_raw, matrix_raw
        np.save(str(npy_path), matrix)
        with open(words_path, "wb") as f:
            pickle.dump(words, f)
        logger.info(f"Migration complete: {len(words):,} {lang} words saved as v3")
    else:
        url = VEC_URLS[lang]
        is_gz = url.endswith(".gz")
        raw_path = CACHE_DIR / (f"{lang}.vec.gz" if is_gz else f"{lang}.vec")

        if not raw_path.exists():
            logger.info(f"Downloading {lang} vectors ({url})...")
            import urllib.request
            urllib.request.urlretrieve(url, str(raw_path))
            logger.info(f"Downloaded: {raw_path.stat().st_size // 1_048_576}MB")

        logger.info(f"Parsing {lang} vectors...")
        words, matrix = _load_vec_file(str(raw_path), MAX_WORDS, language=lang)

        logger.info(f"Caching {lang} vectors as numpy arrays...")
        np.save(str(npy_path), matrix)
        with open(words_path, "wb") as f:
            pickle.dump(words, f)
        raw_path.unlink()
        logger.info(f"Cached and deleted raw file")

    space = _build_space(words, matrix, lang)
    _load_or_compute_good_mask(space, lang)
    return space


def get_word_vector(space: EmbeddingSpace, word: str) -> "np.ndarray | None":
    canonical = normalize_word(word, space.language)
    idx = space.word_to_idx.get(canonical)
    if idx is None:
        return None
    return space.matrix[idx]


def phrase_vec(space: EmbeddingSpace, phrase: str) -> np.ndarray:
    """Average vectors of tokens in a phrase (for multi-word starting pairs)."""
    tokens = phrase.split()
    vecs = []
    for t in tokens:
        canonical = normalize_word(t, space.language)
        idx = space.word_to_idx.get(canonical)
        if idx is not None:
            vecs.append(space.matrix[idx])
    if not vecs:
        raise WordNotFoundError(phrase)
    v = np.mean(vecs, axis=0).astype(np.float32)
    norm = np.linalg.norm(v)
    if norm > 0:
        v /= norm
    return v


def compute_midpoint(space: EmbeddingSpace, word1: str, word2: str) -> np.ndarray:
    v1 = phrase_vec(space, word1)
    v2 = phrase_vec(space, word2)
    mid = v1 + v2
    norm = np.linalg.norm(mid)
    if norm > 0:
        mid /= norm
    return mid.astype(np.float32)


def _is_good_suggestion(word: str, space: "EmbeddingSpace | None" = None,
                        skip_contamination: bool = False) -> bool:
    """Word must be 3-10 letters, not a prefix/plural/construct form, and not too rare.

    `skip_contamination=True` omits ONLY the expensive per-word k-NN neighbour-purity
    check (Hebrew). Because the overall result is a logical AND of every check, the
    contamination flag can be computed separately (batched at load time) and AND-ed back
    in without changing which words pass — see _compute_good_mask.
    """
    if not (3 <= len(word) <= 10):
        return False
    clean = word.replace("'", "").replace("'", "").replace("-", "")
    if not clean.isalpha():
        return False
    if space is not None and space.language == "he":
        # Must be pure Hebrew letters — reject Latin words (wifi, linux, iphone…)
        if not all(c in _HE_LETTERS for c in word):
            return False
        # Reject explicit preposition/pronoun forms (עמה, אליו, ממנו…)
        if word in _HE_PREPOSITION_FORMS:
            return False
        # Reject known historical/geographical proper nouns too common to rank-filter
        if word in _HE_PROPER_NOUN_BLOCKLIST:
            return False
        # Reject sensitive-content terms (sexual/drug/extreme-violence) — see
        # _HE_SENSITIVE_BLOCKLIST. The computer should never be the one steering a
        # casual game toward this territory.
        if word in _HE_SENSITIVE_BLOCKLIST:
            return False
        # Reject Wikipedia username/talk-page artifacts generically: these rank deceptively
        # high (e.g. קיפודנחש at #2107) so the rank filter below can't catch them, but their
        # nearest neighbours are other usernames/handles/hashtags — a signal no genuine
        # Hebrew word exhibits. See _is_neighbor_contaminated.
        if not skip_contamination and _is_neighbor_contaminated(word, space):
            return False
        # Reject masculine plural forms (ים) when singular base is in vocab.
        # len(base) >= 3 guard keeps standalone words: חיים (base חי=2), מים (base מ=1)
        # Also check _with_final(base) to handle אסטרונומ→אסטרונום (non-final→final form)
        if word.endswith('ים') and len(word) >= 5:
            base = word[:-2]
            if len(base) >= 3 and (
                base in space.word_to_idx
                or base + 'ה' in space.word_to_idx
                or _with_final(base) in space.word_to_idx
            ):
                return False
        # Reject feminine plural forms (ות) when singular base is in vocab.
        # Also handles irregular ית→יות (מונית→מוניות): check word[:-2]+'ת'
        if word.endswith('ות') and len(word) >= 5:
            base = word[:-2]
            if len(base) >= 3 and (
                base in space.word_to_idx
                or base + 'ה' in space.word_to_idx
                or base + 'ת' in space.word_to_idx   # ית→יות: מוני+ת = מונית
                or _with_final(base) in space.word_to_idx
            ):
                return False
        # Construct-possessive תו: ארוסתו = ארוסה+ת+ו, ממשלתו = ממשלה+ת+ו
        # base2 = word[:-2]; check base2, base2+"ה", base2+"ת" in vocab
        if word.endswith("תו") and len(word) >= 5:
            base2 = word[:-2]
            if (base2 in space.word_to_idx
                    or base2 + "ה" in space.word_to_idx
                    or base2 + "ת" in space.word_to_idx
                    or _with_final(base2) in space.word_to_idx):
                return False
        # Reject construct-state adjectives (י suffix): פגזי, טילי, רקטי, משגרי…
        # Only filter when the base is a short noun (≤5 chars) in vocab — this keeps
        # ישראלי (base ישראל=6), ירושלמי (base ירושלם=6) while removing פגזי (base פגז=3)
        # Construct-state / adjective "י" suffix: מפציצי→מפציץ, ילדי→ילד, רפואי→רפואה
        # Check base, _with_final(base), and base+"ה" (for adjectives derived from ה-nouns)
        if word.endswith('י') and len(word) >= 4:
            base = word[:-1]
            if len(base) <= 7 and (
                base in space.word_to_idx
                or _with_final(base) in space.word_to_idx
                or base + "ה" in space.word_to_idx
            ):
                return False
        # Query-time fallback for possessive suffixes the load-time filter may miss.
        # Threshold 3 (not 4) to also catch short forms: אמו=אם+ו, בנו=בן+ו
        if len(word) >= 3 and word[-1] == "ו":
            base = word[:-1]
            if base in space.word_to_idx or _with_final(base) in space.word_to_idx:
                return False
        # יה suffix: אחיה=אח+יה, חבריה, שכנותיה. Threshold 4 (not 5) catches short forms.
        if len(word) >= 4 and word[-2:] == "יה":
            base = word[:-2]
            if base in space.word_to_idx or _with_final(base) in space.word_to_idx:
                return False
        # תה possessive suffix (feminine "her"): עבודתה → עבודה
        if len(word) >= 5 and word[-2:] == "תה":
            base = word[:-2]
            if (base in space.word_to_idx or base + "ה" in space.word_to_idx
                    or _with_final(base) in space.word_to_idx):
                return False
        # Skip single-char prefix forms (e.g. ועם = ו+עם, המלך = ה+מלך).
        # Minimum length 4 prevents filtering standalone 3-char nouns like כפר, לחם, כלב, בית.
        # Exception: ו and ה prefixes are filtered at length 3 too — standalone 3-char nouns
        # virtually never start with ו (conjunction) or ה (definite article).
        # This blocks: וגן=ו+גן, ועם=ו+עם, העץ=ה+עץ, החי=ה+חי, etc.
        if word[0] in ("ו", "ה") and len(word) == 3 and word[1:] in space.word_to_idx:
            return False
        if len(word) >= 4 and word[0] in _HE_PREFIXES_1 and word[1:] in space.word_to_idx:
            return False
        # Prefix + internal noun + possessive ה: בבימויה = ב+בימוי+ה
        # Catches prefixed-possessive forms even when only the inner base is in vocab.
        if len(word) >= 5 and word[0] in _HE_PREFIXES_1 and word[-1] == "ה":
            inner = word[1:-1]
            if inner in space.word_to_idx:
                return False
        # Skip two-char prefix forms (e.g. שבמלך = שב+מלך)
        if len(word) >= 5 and word[:2] in _HE_PREFIXES_2 and word[2:] in space.word_to_idx:
            return False
        # Skip uncommon words (> 16th percentile) — removes obscure proper nouns and
        # passive-participle adjectives while keeping common content words.
        idx = space.word_to_idx.get(word)
        if idx is not None and idx > len(space.words) * 0.16:
            return False
        # POS filter: reject verbs and verb-adjectives.
        # Threshold 0.02 catches passive participles (מוגש gap≈+0.028) while
        # keeping nouns — the smallest noun gap observed is דובר at -0.045.
        if space.noun_proto is not None and space.verb_proto is not None and idx is not None:
            w_vec = space.matrix[idx]
            noun_sim = float(np.dot(w_vec, space.noun_proto))
            verb_sim = float(np.dot(w_vec, space.verb_proto))
            if verb_sim > noun_sim + 0.02:
                return False
        # Hebrew infinitives (ל + verb stem, 5+ chars) look noun-like to the POS prototype
        # because they share contexts with verbal nouns. Filter when the word is clearly
        # not noun-dominant (gap < 0.02 in favor of noun).
        if word[0] == 'ל' and len(word) >= 5 and idx is not None:
            if space.noun_proto is not None and space.verb_proto is not None:
                wv = space.matrix[idx]
                ns = float(np.dot(wv, space.noun_proto))
                vs = float(np.dot(wv, space.verb_proto))
                if vs > ns - 0.02:  # not strongly noun → likely infinitive
                    return False
        # Construct-ת: בקעת→בקעה, ממשלת→ממשלה — strip ת and check if base+"ה" in vocab
        if word.endswith('ת') and len(word) >= 4:
            base = word[:-1]
            if base + 'ה' in space.word_to_idx or (len(base) >= 3 and base in space.word_to_idx):
                return False
    if space is not None and space.language == "en":
        # Reject proper nouns (capitalized) — they appear twice in the vocab and
        # look messy as game suggestions
        if word[0].isupper():
            return False
        # Reject sensitive-content terms (sexual/drug/extreme-violence) — see
        # _EN_SENSITIVE_BLOCKLIST. The computer should never be the one steering a
        # casual game toward this territory.
        if word in _EN_SENSITIVE_BLOCKLIST:
            return False
        # Static blocklist for adjectives the prototype can't distinguish from nouns
        if word in _EN_ADJECTIVE_BLOCKLIST:
            return False
        idx = space.word_to_idx.get(word)
        wd = space.word_to_idx  # alias for brevity
        # POS filter: reject verbs, adjectives, adverbs
        if idx is not None and space.noun_proto is not None and space.verb_proto is not None:
            w_vec = space.matrix[idx]
            noun_sim = float(np.dot(w_vec, space.noun_proto))
            verb_sim = float(np.dot(w_vec, space.verb_proto))
            if verb_sim > noun_sim + 0.04:
                return False
        # Plural -s: planets→planet
        if word.endswith('s') and len(word) > 3 and word[:-1] in wd:
            return False
        # Plural -es: churches→church
        if word.endswith('es') and len(word) > 4 and word[:-2] in wd:
            return False
        # Plural -ies: galaxies→galaxy
        if word.endswith('ies') and len(word) > 5 and word[:-3] + 'y' in wd:
            return False
        # Comparative/superlative: slower→slow, fastest→fast
        if word.endswith('er') and len(word) > 4 and word[:-2] in wd:
            return False
        if word.endswith('est') and len(word) > 5 and word[:-3] in wd:
            return False
        # Gerunds/present-participles: running→run
        if word.endswith('ing') and len(word) > 5 and word[:-3] in wd:
            return False
        # Past tense/participle: walked→walk
        if word.endswith('ed') and len(word) > 4 and word[:-2] in wd:
            return False
        # Adjective suffix -al: orbital→orbit, tidal→tide (tide+al skipped, orbit+al=orbital)
        if word.endswith('al') and len(word) > 5 and word[:-2] in wd:
            return False
        # Adjective suffix -ary: planetary→planet
        if word.endswith('ary') and len(word) > 6 and word[:-3] in wd:
            return False
        # Adverb suffix -ly: quickly→quick
        if word.endswith('ly') and len(word) > 4 and word[:-2] in wd:
            return False
        # Rank threshold for English: top 20%
        if idx is not None and idx > len(space.words) * 0.20:
            return False
    return True


def find_best_middle(space: EmbeddingSpace, word1: str, word2: str, exclude: set) -> str:
    """Find the best middle word using min-similarity scoring: min(sim(w,w1), sim(w,w2)).
    This maximises the *weaker* connection, ensuring the result is genuinely balanced
    between both inputs. A floor of 0.25 on each similarity prevents picking
    words that are only weakly related to one endpoint.
    """
    v1 = phrase_vec(space, word1)
    v2 = phrase_vec(space, word2)
    midpoint = v1 + v2
    norm = np.linalg.norm(midpoint)
    if norm > 0:
        midpoint /= norm
    midpoint = midpoint.astype(np.float32)

    pair_sim = float(np.dot(v1, v2))

    # Candidate pool: tighter for similar pairs (avoids random walk in dense domains),
    # wider for dissimilar pairs (sparse midpoint neighbourhood).
    if pair_sim >= 0.55:
        base_n = 300   # e.g. tea+drinks — only pick the most central word
    elif pair_sim >= 0.15:
        base_n = 800
    else:
        base_n = 1200
    n_candidates = min(base_n + len(exclude), len(space.words))
    _, indices = space.nn_index.kneighbors([midpoint], n_neighbors=n_candidates)

    # When the pair is already very similar (converging), relax ceiling; otherwise tighten
    # to prevent words glued to one cluster.
    sim_ceiling = 0.72 if pair_sim > 0.60 else 0.58

    # Adaptive floor: for very dissimilar pairs the midpoint neighbourhood is sparse
    # and balanced words naturally have lower endpoint similarities.
    if pair_sim >= 0.30:
        MIN_FLOOR = 0.25
    elif pair_sim >= 0.15:
        MIN_FLOOR = 0.20
    else:
        MIN_FLOOR = 0.17

    best_word, best_score = None, -1.0
    for idx in indices[0]:
        word = space.words[idx]
        if word in exclude or not _is_good_idx(space, idx):
            continue
        w_vec = space.matrix[idx]
        s1 = float(np.dot(w_vec, v1))
        s2 = float(np.dot(w_vec, v2))
        if s1 < MIN_FLOOR or s2 < MIN_FLOOR:
            continue
        if s1 > sim_ceiling or s2 > sim_ceiling:
            continue
        score = min(s1, s2)
        if score > best_score:
            best_score = score
            best_word = word

    if best_word is None:
        # Fallback 1: drop ceiling, keep adaptive floor
        for idx in indices[0]:
            word = space.words[idx]
            if word in exclude or not _is_good_idx(space, idx):
                continue
            w_vec = space.matrix[idx]
            s1 = float(np.dot(w_vec, v1))
            s2 = float(np.dot(w_vec, v2))
            if s1 >= MIN_FLOOR and s2 >= MIN_FLOOR:
                return word

    if best_word is None:
        # Fallback 2: absolute minimum — any word related to at least one endpoint
        for idx in indices[0]:
            word = space.words[idx]
            if word in exclude or not _is_good_idx(space, idx):
                continue
            w_vec = space.matrix[idx]
            s1 = float(np.dot(w_vec, v1))
            s2 = float(np.dot(w_vec, v2))
            if s1 >= 0.15 and s2 >= 0.15:
                return word

    return best_word


def get_hints(space: EmbeddingSpace, word1: str, word2: str, n_hints: int = 3) -> list:
    """Return hint words (ranks 5-8 near midpoint, skipping top 4 to not give away the answer).
    Uses a larger pool (300) because strict quality filters reject many candidates."""
    midpoint = compute_midpoint(space, word1, word2)
    exclude = _phrase_tokens(space, word1) | _phrase_tokens(space, word2)
    n_pool = min(300 + len(exclude), len(space.words))
    _, indices = space.nn_index.kneighbors([midpoint], n_neighbors=n_pool)
    hints = []
    seen_normalized = set()
    rank = 0
    for idx in indices[0]:
        word = space.words[idx]
        if word in exclude or not _is_good_idx(space, idx):
            continue
        # Deduplicate: collapse common Hebrew spelling variants (וו→ו, יי→י)
        normalized = normalize_word(word, space.language)
        if space.language == "he":
            normalized = normalized.replace("וו", "ו").replace("יי", "י")
        if normalized in seen_normalized:
            continue
        rank += 1
        seen_normalized.add(normalized)
        if rank >= 5 and len(hints) < n_hints:
            hints.append(word)
        if len(hints) >= n_hints:
            break
    return hints


def _phrase_tokens(space: EmbeddingSpace, phrase: str) -> set:
    """All canonical tokens that make up a phrase (handles multi-word like 'תל אביב')."""
    tokens = set()
    tokens.add(normalize_word(phrase, space.language))
    for t in phrase.split():
        tokens.add(normalize_word(t, space.language))
    return tokens
