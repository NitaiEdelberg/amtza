import random
from typing import Optional, Dict

# Every pair here was auditioned before being added: both words checked against the
# vocabulary, and the computer's opening answer inspected (scripts/playtest.py pairs).
# A pair whose first answer is jarring makes the game look broken on the one round a
# new player is most likely to judge it on, so candidates that opened on a strange
# word were dropped rather than kept and filtered around. The comment on each line is
# the answer the computer actually gives.
STARTING_PAIRS = [
    # ── Hebrew ────────────────────────────────────────────────────────────────
    {"word1": "שמש", "word2": "ירח", "language": "he"},        # → כוכב
    {"word1": "מלך", "word2": "חייל", "language": "he"},        # → שליט
    {"word1": "כלב", "word2": "חתול", "language": "he"},        # → ארנב
    {"word1": "שבת", "word2": "קפה", "language": "he"},         # → צהריים
    {"word1": "אמא", "word2": "ילד", "language": "he"},         # → ילדה
    {"word1": "חומוס", "word2": "פיצה", "language": "he"},      # → גלידה
    {"word1": "כסף", "word2": "אהבה", "language": "he"},        # → נדיבות
    {"word1": "ילד", "word2": "זקן", "language": "he"},         # → צעיר
    {"word1": "יום", "word2": "ליל", "language": "he"},         # → חצות
    {"word1": "חם", "word2": "קר", "language": "he"},           # → קריר
    {"word1": "עיר", "word2": "כפר", "language": "he"},         # → טירה
    {"word1": "שיר", "word2": "ריקוד", "language": "he"},       # → מנגינה
    {"word1": "ספר", "word2": "ילד", "language": "he"},         # → תלמיד
    {"word1": "רופא", "word2": "חולה", "language": "he"},       # → טיפול
    {"word1": "אש", "word2": "מים", "language": "he"},          # → כיריים
    {"word1": "קרב", "word2": "ניצחון", "language": "he"},      # → תבוסה
    {"word1": "סרט", "word2": "תיאטרון", "language": "he"},     # → קולנוע
    {"word1": "חורף", "word2": "קיץ", "language": "he"},        # → סתיו
    {"word1": "בוקר", "word2": "לילה", "language": "he"},       # → יום
    {"word1": "מלח", "word2": "סוכר", "language": "he"},        # → חומץ
    {"word1": "ספר", "word2": "סרט", "language": "he"},         # → רומן
    {"word1": "מוזיקה", "word2": "ריקוד", "language": "he"},    # → מנגינה
    {"word1": "אבא", "word2": "סבא", "language": "he"},         # → סבתא
    {"word1": "כדורגל", "word2": "טניס", "language": "he"},     # → ספורט
    {"word1": "מכונית", "word2": "אופניים", "language": "he"},  # → אופנוע
    {"word1": "מחשב", "word2": "טלפון", "language": "he"},      # → נייד
    {"word1": "חייל", "word2": "שוטר", "language": "he"},       # → אזרח
    {"word1": "אריה", "word2": "חתול", "language": "he"},       # → נמר
    {"word1": "הר", "word2": "עמק", "language": "he"},          # → גבעה
    {"word1": "נהר", "word2": "ים", "language": "he"},          # → מפרץ
    {"word1": "חלון", "word2": "דלת", "language": "he"},        # → חדר
    {"word1": "שולחן", "word2": "כיסא", "language": "he"},      # → רהיט
    {"word1": "שמחה", "word2": "עצב", "language": "he"},        # → כעס
    {"word1": "זהב", "word2": "ברזל", "language": "he"},        # → נחושת
    {"word1": "תינוק", "word2": "זקן", "language": "he"},       # → נער
    {"word1": "קפה", "word2": "תה", "language": "he"},          # → סוכר
    {"word1": "תפוח", "word2": "בננה", "language": "he"},       # → אננס
    {"word1": "מלך", "word2": "מלכה", "language": "he"},        # → נסיכה

    # ── English ───────────────────────────────────────────────────────────────
    {"word1": "ocean", "word2": "mountain", "language": "en"},   # → lake
    {"word1": "love", "word2": "war", "language": "en"},         # → quarrel
    {"word1": "fire", "word2": "ice", "language": "en"},         # → lava
    {"word1": "morning", "word2": "night", "language": "en"},    # → evening
    {"word1": "king", "word2": "peasant", "language": "en"},     # → princess
    {"word1": "silence", "word2": "thunder", "language": "en"},  # → fury
    {"word1": "city", "word2": "forest", "language": "en"},      # → park
    {"word1": "sun", "word2": "moon", "language": "en"},         # → sky
    {"word1": "past", "word2": "future", "language": "en"},      # → present
    {"word1": "cat", "word2": "dog", "language": "en"},          # → pet
    {"word1": "coffee", "word2": "sleep", "language": "en"},     # → morning
    {"word1": "gold", "word2": "silver", "language": "en"},      # → copper
    {"word1": "earth", "word2": "sky", "language": "en"},        # → heaven
    {"word1": "winter", "word2": "summer", "language": "en"},    # → autumn
    {"word1": "soldier", "word2": "peace", "language": "en"},    # → war
    {"word1": "child", "word2": "elder", "language": "en"},      # → father
    {"word1": "salt", "word2": "sugar", "language": "en"},       # → vinegar
    {"word1": "book", "word2": "film", "language": "en"},        # → story
    {"word1": "music", "word2": "dance", "language": "en"},      # → theatre
    {"word1": "river", "word2": "sea", "language": "en"},        # → shore
    {"word1": "hill", "word2": "valley", "language": "en"},      # → mountain
    {"word1": "table", "word2": "chair", "language": "en"},      # → stool
    {"word1": "gold", "word2": "iron", "language": "en"},        # → copper
    {"word1": "baby", "word2": "elder", "language": "en"},       # → mother
    {"word1": "coffee", "word2": "tea", "language": "en"},       # → cup
    {"word1": "car", "word2": "bicycle", "language": "en"},      # → motorcycle
    {"word1": "computer", "word2": "phone", "language": "en"},   # → device
    {"word1": "lion", "word2": "cat", "language": "en"},         # → animal
    {"word1": "rain", "word2": "sun", "language": "en"},         # → wind
    {"word1": "spring", "word2": "autumn", "language": "en"},    # → summer
    {"word1": "guitar", "word2": "drum", "language": "en"},      # → rhythm
    {"word1": "mountain", "word2": "desert", "language": "en"},  # → canyon
    {"word1": "knife", "word2": "spoon", "language": "en"},      # → fork
    {"word1": "bee", "word2": "flower", "language": "en"},       # → butterfly
    {"word1": "wine", "word2": "milk", "language": "en"},        # → cheese
    {"word1": "paper", "word2": "pencil", "language": "en"},     # → notebook
    {"word1": "chess", "word2": "football", "language": "en"},   # → tennis
    {"word1": "fear", "word2": "courage", "language": "en"},     # → cowardice
    {"word1": "bread", "word2": "butter", "language": "en"},     # → flour
    {"word1": "teacher", "word2": "student", "language": "en"},  # → school
    {"word1": "doctor", "word2": "nurse", "language": "en"},     # → hospital
    {"word1": "apple", "word2": "tree", "language": "en"},       # → orchard
]


def get_random_pair(lang: Optional[str] = None) -> Dict:
    if lang:
        filtered = [p for p in STARTING_PAIRS if p["language"] == lang]
        if filtered:
            return random.choice(filtered)
    return random.choice(STARTING_PAIRS)
