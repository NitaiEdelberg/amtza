import asyncio
import logging
import os
from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from embeddings import (
    EmbeddingSpace,
    WordNotFoundError,
    compute_midpoint,
    detect_language,
    find_nearest,
    get_hints,
    get_word_vector,
    load_or_download_sync,
    normalize_word,
)
from game import build_round_result
from word_pairs import get_random_pair

load_dotenv()
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

spaces: dict[str, EmbeddingSpace] = {}
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
        # Keep models_loaded=False; health endpoint reports not ready
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
async def pair(lang: str | None = None):
    return get_random_pair(lang)


class GuessRequest(BaseModel):
    word1: str
    word2: str
    player_guess: str
    round_num: int = 1


@app.post("/guess")
async def guess(req: GuessRequest):
    _require_models()

    lang = detect_language(req.word1)
    if lang not in spaces:
        raise HTTPException(500, f"No embedding space for language: {lang}")
    space = spaces[lang]

    # Validate and canonicalize player's guess
    player_canonical = normalize_word(req.player_guess, lang)
    player_vec = get_word_vector(space, player_canonical)
    if player_vec is None:
        raise HTTPException(
            422,
            detail={
                "error": "word_not_found",
                "message": f"המילה '{req.player_guess}' לא נמצאה במילון" if lang == "he"
                           else f"Word '{req.player_guess}' not found in vocabulary",
                "word": req.player_guess,
            },
        )

    # Cannot guess the words that are already in the pair
    pair_canonical = {normalize_word(req.word1, lang), normalize_word(req.word2, lang)}
    if player_canonical in pair_canonical:
        raise HTTPException(
            422,
            detail={
                "error": "same_as_pair",
                "message": "הניחוש חייב להיות שונה מהמילים הקיימות" if lang == "he"
                           else "Your guess must be different from the current pair words",
            },
        )

    # Compute midpoint and computer's guess
    try:
        midpoint = compute_midpoint(space, req.word1, req.word2)
    except WordNotFoundError as e:
        raise HTTPException(422, detail={"error": "pair_word_not_found", "message": str(e)})

    computer_guess = find_nearest(space, midpoint, exclude=pair_canonical | {player_canonical})
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
    valid = canonical in space.word_to_idx
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
