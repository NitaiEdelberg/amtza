import asyncio
import logging
import os
from contextlib import asynccontextmanager
from typing import Dict, List, Optional

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from embeddings import (
    EmbeddingSpace,
    WordNotFoundError,
    compute_midpoint,
    detect_language,
    find_best_middle,
    get_hints,
    get_word_vector,
    is_valid_word,
    load_or_download_sync,
    normalize_word,
    phrase_vec,
    _phrase_tokens,
)
from game import build_round_result
from word_pairs import get_random_pair

load_dotenv()
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

spaces: Dict[str, EmbeddingSpace] = {}
models_loaded = False


@asynccontextmanager
async def lifespan(app: FastAPI):
    global models_loaded
    logger.info("Loading embedding models...")
    loop = asyncio.get_event_loop()
    try:
        he_space, en_space = await asyncio.gather(
            loop.run_in_executor(None, load_or_download_sync, "he"),
            loop.run_in_executor(None, load_or_download_sync, "en"),
        )
        spaces["he"] = he_space
        spaces["en"] = en_space
        models_loaded = True
        logger.info("Both embedding models loaded successfully")
    except Exception as e:
        logger.error(f"Failed to load models: {e}")
    yield
    spaces.clear()


app = FastAPI(title="אמצע API — Amtza Game", version="1.0.0", lifespan=lifespan)

allowed_origin = os.getenv("ALLOWED_ORIGIN", "*")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[allowed_origin] if allowed_origin != "*" else ["*"],
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


def _require_models():
    if not models_loaded:
        raise HTTPException(503, "Models are still loading, please wait")


# ── Routes ────────────────────────────────────────────────────────────────────

@app.get("/health")
async def health():
    return {"status": "ok", "models_loaded": models_loaded}


@app.get("/pair")
async def pair(lang: Optional[str] = None):
    return get_random_pair(lang)


class GuessRequest(BaseModel):
    word1: str
    word2: str
    player_guess: str
    round_num: int = 1
    used_words: List[str] = []


@app.post("/guess")
async def guess(req: GuessRequest):
    _require_models()

    lang = detect_language(req.word1)
    if lang not in spaces:
        raise HTTPException(500, f"No embedding space for language: {lang}")
    space = spaces[lang]

    # normalize_word preserves spaces so multi-word phrases stay intact ("אייל גולן" → "אייל גולן")
    player_canonical = normalize_word(req.player_guess, lang)
    try:
        player_vec = phrase_vec(space, player_canonical)
    except WordNotFoundError:
        raise HTTPException(
            422,
            detail={
                "error": "word_not_found",
                "message": f"המילה '{req.player_guess}' לא נמצאה במילון" if lang == "he"
                           else f"Word '{req.player_guess}' not found in vocabulary",
                "word": req.player_guess,
            },
        )

    # Exclude all tokens from multi-word phrases (e.g. "תל" and "אביב" from "תל אביב")
    pair_tokens = _phrase_tokens(space, req.word1) | _phrase_tokens(space, req.word2)
    if player_canonical in pair_tokens:
        raise HTTPException(
            422,
            detail={
                "error": "same_as_pair",
                "message": "הניחוש חייב להיות שונה מהמילים הקיימות" if lang == "he"
                           else "Your guess must be different from the current pair words",
            },
        )

    # Expand multi-word used words into individual tokens so the computer doesn't
    # re-suggest any component of a phrase the player or computer already played.
    used_canonical: set = set()
    for w in req.used_words:
        used_canonical |= _phrase_tokens(space, w)
    # Do NOT exclude player_canonical — if computer independently picks the same word,
    # that's the win condition. Only exclude pair words and already-used words.
    exclude = pair_tokens | used_canonical

    try:
        midpoint = compute_midpoint(space, req.word1, req.word2)
        computer_guess = find_best_middle(space, req.word1, req.word2, exclude=exclude)
    except WordNotFoundError as e:
        raise HTTPException(422, detail={"error": "pair_word_not_found", "message": str(e)})

    if computer_guess is None:
        # Extremely rare: the exclusion set has grown so large no valid middle word
        # remains nearby. Surface a clean error instead of crashing on a None vector.
        raise HTTPException(
            422,
            detail={
                "error": "no_middle_word",
                "message": "המחשב לא מצא מילה מתאימה לאמצע — נסו זוג מילים חדש" if lang == "he"
                           else "The computer couldn't find a middle word — try a new pair",
            },
        )

    computer_vec = get_word_vector(space, computer_guess)

    result = build_round_result(
        round_num=req.round_num,
        word1=req.word1,
        word2=req.word2,
        player_guess=player_canonical,
        computer_guess=computer_guess,
        player_vec=player_vec,
        computer_vec=computer_vec,
        midpoint=midpoint,
        lang=lang,
    )

    return {
        "computer_guess": result.computer_guess,
        "player_guess": result.player_guess,
        "player_similarity": result.player_similarity,
        "computer_similarity": result.computer_similarity,
        "player_computer_similarity": result.player_computer_similarity,
        "is_won": result.is_won,
        "new_pair": [result.player_guess, result.computer_guess],
        "funny_message": result.funny_message,
        "win_message": result.win_message,
        "language": result.language,
    }


@app.get("/validate/{word}")
async def validate(word: str):
    _require_models()
    lang = detect_language(word)
    space = spaces[lang]
    canonical = normalize_word(word, lang)
    valid = is_valid_word(space, word)
    return {"valid": valid, "canonical": canonical, "language": lang}


class HintRequest(BaseModel):
    word1: str
    word2: str


@app.post("/hint")
async def hint(req: HintRequest):
    _require_models()
    lang = detect_language(req.word1)
    space = spaces[lang]
    try:
        hints = get_hints(space, req.word1, req.word2)
    except WordNotFoundError as e:
        raise HTTPException(422, detail={"error": "word_not_found", "message": str(e)})
    return {"hints": hints, "language": lang}
