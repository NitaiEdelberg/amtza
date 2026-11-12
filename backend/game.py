import random
from dataclasses import dataclass
from typing import Optional

import numpy as np

# The real game is won when both sides say the SAME word. A similarity-based win is
# a convergence aid, so the bar has to stay high enough that the two words are
# genuinely interchangeable. Measured fastText cosines: mother/father 0.83,
# brother/father 0.79, cat/dog 0.71, king/queen 0.71 — all *related opposites*, not
# the same idea. At the old 0.70 bar every one of those "won", and the game then told
# the player "you and the computer thought the same thing", which was simply untrue.
# 0.85 keeps near-synonyms winning while related-but-different pairs keep playing.
WIN_THRESHOLD = 0.85

# "Homing" mechanism: nearest-neighbour midpoint search has no anchor to the original
# pair, so a run of unlucky guesses can occasionally drift through a long chain of
# locally-plausible-but-globally-irrelevant clusters (cities → historical figures →
# mythology → astronomy → math…) for 30-50+ rounds without ever crossing WIN_THRESHOLD.
# Past a grace period, gradually relax the win bar each round so every game is
# guaranteed to converge in a bounded number of rounds — like two people who keep
# circling back to the same general territory eventually just calling it a match.
# The floor stays at 0.72: below that the two words are visibly different things and
# declaring a match feels like the game giving up rather than converging.
#
# Measured over 330 simulated games (scripts/simulate_games.py, 10 per starting
# pair, 60-round cap): 327/330 converge, median 5 rounds, p95 22, 6.1% run past 20.
# Loosening to decay=0.015 / floor=0.65 was tried and rejected — it moved the
# median not at all and the long tail barely (6.1% -> 5.5%, still the same 3
# stragglers), while accepting word pairs *less* alike than cat/dog (0.708). The
# tail comes from games genuinely wandering, not from the floor being too high.
HOMING_GRACE_ROUNDS = 8
HOMING_DECAY_PER_ROUND = 0.01
HOMING_MIN_THRESHOLD = 0.72


def _effective_threshold(round_num: int) -> float:
    if round_num <= HOMING_GRACE_ROUNDS:
        return WIN_THRESHOLD
    relaxed = WIN_THRESHOLD - HOMING_DECAY_PER_ROUND * (round_num - HOMING_GRACE_ROUNDS)
    return max(HOMING_MIN_THRESHOLD, relaxed)

# Keyed to how close the two guesses were, the same number the reveal shows. They
# used to be keyed to the player's distance from the pair's midpoint, a number the
# screen no longer shows, so a play-tester got "close!" at 11% and "really close to
# the middle" right before a word that had nothing to do with theirs. Nothing here
# claims the computer was "more precise" either: there is no right answer to be
# more precise about, and saying so read as smug.
FUNNY_MESSAGES_HE = {
    "very_far": [
        "חשבנו על דברים שונים לגמרי 🗺️",
        "כל אחד הלך לכיוון אחר. סיבוב הבא! 🔄",
        "יצירתי! אבל המחשב חשב על משהו אחר לגמרי 🎨",
        "רחוקים... אבל עכשיו יש זוג חדש לגמרי 🚀",
    ],
    "far": [
        "עוד לא באותו ראש, אבל מתקרבים 🤷",
        "כיוון שונה, נסו לחשוב על מה שמחבר את שתיהן 💡",
        "לא באותו מקום, אבל לא נואש! 💪",
    ],
    "medium": [
        "קרוב! אתם באותו תחום 🎯",
        "חושבים דומה! עוד קצת 🔥",
        "ממש מתקרבים 🌟",
    ],
    "close": [
        "כמעט! כמעט אותה מילה 😮",
        "וואו, הייתם ממש קרובים 🤏",
    ],
}

FUNNY_MESSAGES_EN = {
    "very_far": [
        "Totally different wavelengths 🗺️",
        "You went one way, the computer went the other 🔄",
        "Creative! The computer was thinking of something else entirely 🎨",
    ],
    "far": [
        "Not on the same page yet, but getting there 🤷",
        "Different angles. Think about what links the two words 💡",
        "Not there yet, keep going! 💪",
    ],
    "medium": [
        "Close! You're in the same area 🎯",
        "Great minds think alike... almost 🔥",
        "Getting really close 🌟",
    ],
    "close": [
        "So close! Almost the same word 😮",
        "Ooh, nearly had it 🤏",
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
    "מושלם! 🌟 המחשב ואתם חשבתם אותו דבר!",
    "יאללה! 🎊 הגעתם לאמצע ביחד!",
    "בום! 💥 זה בדיוק האמצע!",
]

WIN_MESSAGES_EN = [
    "We did it! 🎉 Found the middle!",
    "Perfect! 🌟 You and the computer thought the same thing!",
    "Yes! 🎊 We met in the middle!",
    "Boom! 💥 That's exactly the middle!",
]

# Shown when the game ends on *similarity* rather than the identical word. These must
# never claim the two words were the same — they say the words were close enough, and
# name both, so the player can see exactly what happened.
NEAR_WIN_MESSAGES_HE = [
    "מספיק קרוב! 🎯 '{a}' ו'{b}' זה כמעט אותו דבר.",
    "סגרנו! 🤝 '{a}' ו'{b}' — בעצם אותו רעיון.",
    "כמעט מילה במילה! ✨ '{a}' מול '{b}' — נחשב!",
]

NEAR_WIN_MESSAGES_EN = [
    "Close enough! 🎯 '{a}' and '{b}' are practically the same idea.",
    "That'll do! 🤝 '{a}' vs '{b}' — near enough to call it.",
    "Almost word for word! ✨ '{a}' and '{b}' — we'll take it.",
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


_HE_FINAL_TO_REGULAR = {"ך": "כ", "ם": "מ", "ן": "נ", "ף": "פ", "ץ": "צ"}


def _surface_forms(word: str) -> set:
    """The word plus the forms a person means as "the same word".

    Only regular, unambiguous inflections: the Hebrew definite article and the
    ־ים/־ות plurals, English -s/-es/-ies. A player who types ילדים or apples against
    the computer's ילד or apple said the same thing, and losing that round on
    spelling feels like the game cheating. Irregular plurals (פרי/פירות) are left to
    the similarity check; guessing them by rule would join unrelated words.
    """
    w = word.strip().lower()
    forms = {w}
    if any("\u0590" <= c <= "\u05ff" for c in w):
        if w.startswith("ה") and len(w) >= 3:
            forms.add(w[1:])
        for base in list(forms):
            stem = base[:-1] + _HE_FINAL_TO_REGULAR.get(base[-1], base[-1]) if base else base
            forms.update({stem + "ים", stem + "ות"})
            if base.endswith(("ה", "ת")) and len(base) >= 3:
                forms.add(base[:-1] + "ות")
            if base.endswith(("ים", "ות")) and len(base) >= 4:
                forms.add(base[:-2])
    else:
        forms.update({w + "s", w + "es"})
        if w.endswith("y") and len(w) >= 3:
            forms.add(w[:-1] + "ies")
        if w.endswith("ies") and len(w) >= 5:
            forms.add(w[:-3] + "y")
        elif w.endswith("es") and len(w) >= 4:
            forms.add(w[:-2])
        if w.endswith("s") and len(w) >= 4:
            forms.add(w[:-1])
    return forms


def same_word(a: str, b: str) -> bool:
    """Whether two guesses are the same word up to a regular plural or article."""
    if a.strip().lower() == b.strip().lower():
        return True
    return b.strip().lower() in _surface_forms(a) or a.strip().lower() in _surface_forms(b)


def check_win(
    player_word: str,
    computer_word: str,
    player_vec: "np.ndarray",
    computer_vec: "np.ndarray",
    round_num: int = 1,
) -> bool:
    if same_word(player_word, computer_word):
        return True
    sim = float(np.dot(player_vec, computer_vec))
    return sim > _effective_threshold(round_num)


def get_funny_message(similarity: float, lang: str, word1: str, word2: str) -> Optional[str]:
    """Message for a round that wasn't won; `similarity` is player-vs-computer."""
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
    return random.choice(messages["close"])


def get_win_message(lang: str, exact: bool = True,
                    player_word: str = "", computer_word: str = "") -> str:
    """Win message. `exact` distinguishes a true same-word win from a similarity win.

    Only an exact match may claim the two sides "thought the same thing" — a
    similarity win names both words instead, so the message is always truthful.
    """
    if exact:
        return random.choice(WIN_MESSAGES_HE if lang == "he" else WIN_MESSAGES_EN)
    msgs = NEAR_WIN_MESSAGES_HE if lang == "he" else NEAR_WIN_MESSAGES_EN
    return random.choice(msgs).format(a=player_word, b=computer_word)


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
    is_exact = same_word(player_guess, computer_guess)
    funny_msg = None if is_won else get_funny_message(player_computer_sim, lang, word1, word2)
    win_msg = (
        get_win_message(lang, exact=is_exact,
                        player_word=player_guess, computer_word=computer_guess)
        if is_won else None
    )
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
