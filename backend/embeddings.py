import os
import gzip
import pickle
import logging
import asyncio
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from sklearn.neighbors import NearestNeighbors

logger = logging.getLogger(__name__)

CACHE_DIR = Path(os.getenv("MODEL_CACHE_DIR", "/data/models"))

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


def _load_vec_file(path: str, max_words: int = MAX_WORDS) -> tuple:
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
            if len(parts) < 302:
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
    return EmbeddingSpace(words=words, word_to_idx=word_to_idx, matrix=matrix, nn_index=nn, language=language)


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
    npy_path = CACHE_DIR / f"{lang}.npy"
    words_path = CACHE_DIR / f"{lang}_words.pkl"

    if npy_path.exists() and words_path.exists():
        logger.info(f"Loading cached {lang} embeddings from {CACHE_DIR}...")
        matrix = np.load(str(npy_path))
        with open(words_path, "rb") as f:
            words = pickle.load(f)
        logger.info(f"Loaded {len(words):,} {lang} words from cache")
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
        words, matrix = _load_vec_file(str(raw_path), MAX_WORDS)

        logger.info(f"Caching {lang} vectors as numpy arrays...")
        np.save(str(npy_path), matrix)
        with open(words_path, "wb") as f:
            pickle.dump(words, f)
        raw_path.unlink()
        logger.info(f"Cached and deleted raw file")

    return _build_space(words, matrix, lang)


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


def find_nearest(space: EmbeddingSpace, query_vec: np.ndarray, exclude: set, n: int = 20) -> str:
    distances, indices = space.nn_index.kneighbors([query_vec], n_neighbors=min(n + len(exclude), len(space.words)))
    for idx in indices[0]:
        word = space.words[idx]
        if word not in exclude:
            return word
    # Brute force fallback
    sims = space.matrix @ query_vec
    for idx in np.argsort(-sims):
        if space.words[idx] not in exclude:
            return space.words[idx]
    raise WordNotFoundError("No neighbor found outside exclusion set")


def get_hints(space: EmbeddingSpace, word1: str, word2: str, n_hints: int = 3) -> list:
    """Return hint words ranked 5-8 nearest to midpoint (not top 4 — too revealing)."""
    midpoint = compute_midpoint(space, word1, word2)
    exclude = {normalize_word(word1, space.language), normalize_word(word2, space.language)}
    distances, indices = space.nn_index.kneighbors([midpoint], n_neighbors=15 + len(exclude))
    hints = []
    rank = 0
    for idx in indices[0]:
        word = space.words[idx]
        if word in exclude:
            continue
        rank += 1
        if rank >= 5 and len(hints) < n_hints:
            hints.append(word)
        if len(hints) >= n_hints:
            break
    return hints
