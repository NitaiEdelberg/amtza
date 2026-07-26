import random
from dataclasses import dataclass
from typing import Optional

import numpy as np

WIN_THRESHOLD = 0.70

# "Homing" mechanism: nearest-neighbour midpoint search has no anchor to the original
# pair, so a run of unlucky guesses can occasionally drift through a long chain of
# locally-plausible-but-globally-irrelevant clusters (cities → historical figures →
# mythology → astronomy → math…) for 30-50+ rounds without ever crossing WIN_THRESHOLD.
# Past a grace period, gradually relax the win bar each round so every game is
# guaranteed to converge in a bounded number of rounds — like two people who keep
# circling back to the same general territory eventually just calling it a match.
HOMING_GRACE_ROUNDS = 10
HOMING_DECAY_PER_ROUND = 0.025
HOMING_MIN_THRESHOLD = 0.50


def _effective_threshold(round_num: int) -> float:
    if round_num <= HOMING_GRACE_ROUNDS:
        return WIN_THRESHOLD
    relaxed = WIN_THRESHOLD - HOMING_DECAY_PER_ROUND * (round_num - HOMING_GRACE_ROUNDS)
    return max(HOMING_MIN_THRESHOLD, relaxed)

FUNNY_MESSAGES_HE = {
    "very_far": [
        "אה... אתה בכיוון אחר לגמרי 🗺️",
        "המחשב שואל: מאיזה כיוון הגעת? 🤔",
        "זה... מעניין. אבל לא ממש קרוב 😅",
        "הניחוש הזה יצא מאיפשהו מאוד רחוק 🚀",
        "יצירתי! אבל... לא ממש באמצע 🎨",
    ],
    "far": [
        "מעניין... אבל לא ממש באמצע 🤷",
        "ניסיון יפה, אבל המחשב לא מסכים 💻",
        "אתה חושב בכיוון אחר מהמחשב 🔄",
        "רחוק קצת מהאמצע, אבל לא נואש! 💪",
    ],
    "medium": [
        "קרוב! אבל המחשב קצת יותר מדויק 🎯",
        "לא רע! עוד ניסיון 🔥",
        "ממש קרוב לאמצע — תמשיך! 🌟",
        "אתה בכיוון הנכון! 👍",
    ],
}

FUNNY_MESSAGES_EN = {
    "very_far": [
        "Hmm... that came from a different galaxy 🚀",
        "The computer is confused by your logic 🤔",
        "Creative! But... not quite in the middle 🎨",
        "That word wandered in from somewhere else entirely 🗺️",
    ],
    "far": [
        "Interesting direction, but not quite there 🤷",
        "The computer begs to differ 💻",
        "You're thinking differently than the algorithm 🔄",
        "Not quite the middle — but don't give up! 💪",
    ],
    "medium": [
        "Close! The computer was a bit more precise 🎯",
        "Not bad! Keep going 🔥",
        "Almost at the midpoint — you're getting it! 🌟",
        "Right direction! 👍",
    ],
}

EASTER_EGGS = {
    frozenset({"חביתה", "ביצה"}): "מחזור אכזרי... מה קדם למה? 🐔🥚",
    frozenset({"שלום", "מלחמה"}): "שנסיים עם שלום, בסוף... ✌️",
    frozenset({"אמא", "אבא"}): "ביחד או לחוד? 👨‍👩‍👧",
    frozenset({"ים", "חול"}): "חופשה! 🏖️",
    frozenset({"love", "hate"}): "Freud would be proud. 🛋️",
    frozenset({"cat", "internet"}): "You know exactly where this is going 🐱",
    frozenset({"fire", "ice"}): "A Song of... 🐉",
    frozenset({"day", "night"}): "Somewhere, someone is sleeping 🌙",
    frozenset({"sun", "moon"}): "Are you an astronomer? 🔭",
    frozenset({"morning", "coffee"}): "Same energy ☕",
}

WIN_MESSAGES_HE = [
    "ניצחנו! 🎉 הגעתם לאמצע!",
    "מושלם! 🌟 המחשב ואתה חשבתם אותו דבר!",
    "יאללה! 🎊 הגעתם לאמצע ביחד!",
    "בום! 💥 זה בדיוק האמצע!",
]

WIN_MESSAGES_EN = [
    "We did it! 🎉 Found the middle!",
    "Perfect! 🌟 You and the computer thought the same thing!",
    "Yes! 🎊 Convergence achieved!",
    "Boom! 💥 That's exactly the middle!",
]


@dataclass
class RoundResult:
    round_num: int
    word1: str
    word2: str
    player_guess: str
    computer_guess: str
    player_similarity: float
    computer_similarity: float
    player_computer_similarity: float
    is_won: bool
    funny_message: Optional[str]
    win_message: Optional[str]
    language: str


def check_win(
    player_word: str,
    computer_word: str,
    player_vec: "np.ndarray",
    computer_vec: "np.ndarray",
    round_num: int = 1,
) -> bool:
    if player_word.lower() == computer_word.lower():
        return True
    sim = float(np.dot(player_vec, computer_vec))
    return sim > _effective_threshold(round_num)


def get_funny_message(similarity: float, lang: str, word1: str, word2: str) -> Optional[str]:
    egg_key = frozenset({word1.lower(), word2.lower()})
    if egg_key in EASTER_EGGS:
        return EASTER_EGGS[egg_key]

    messages = FUNNY_MESSAGES_HE if lang == "he" else FUNNY_MESSAGES_EN

    if similarity < 0.15:
        return random.choice(messages["very_far"])
    elif similarity < 0.30:
        return random.choice(messages["far"])
    elif similarity < 0.45:
        return random.choice(messages["medium"])
    return None


def get_win_message(lang: str) -> str:
    msgs = WIN_MESSAGES_HE if lang == "he" else WIN_MESSAGES_EN
    return random.choice(msgs)


def build_round_result(
    round_num: int,
    word1: str,
    word2: str,
    player_guess: str,
    computer_guess: str,
    player_vec: "np.ndarray",
    computer_vec: "np.ndarray",
    midpoint: "np.ndarray",
    lang: str,
) -> RoundResult:
    player_sim = float(np.dot(player_vec, midpoint))
    computer_sim = float(np.dot(computer_vec, midpoint))
    player_computer_sim = float(np.dot(player_vec, computer_vec))
    is_won = check_win(player_guess, computer_guess, player_vec, computer_vec, round_num)
    funny_msg = None if is_won else get_funny_message(player_sim, lang, word1, word2)
    win_msg = get_win_message(lang) if is_won else None
    return RoundResult(
        round_num=round_num,
        word1=word1,
        word2=word2,
        player_guess=player_guess,
        computer_guess=computer_guess,
        player_similarity=round(player_sim, 4),
        computer_similarity=round(computer_sim, 4),
        player_computer_similarity=round(player_computer_sim, 4),
        is_won=is_won,
        funny_message=funny_msg,
        win_message=win_msg,
        language=lang,
    )
