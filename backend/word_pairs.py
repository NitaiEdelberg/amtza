import random
from typing import Optional, Dict

STARTING_PAIRS = [
    # Hebrew pairs (all words verified in-vocab)
    {"word1": "שמש", "word2": "ירח", "language": "he"},
    {"word1": "מנהיג", "word2": "גיבור", "language": "he"},
    {"word1": "כלב", "word2": "חתול", "language": "he"},      # dog+cat → pet animal
    {"word1": "שבת", "word2": "קפה", "language": "he"},      # Shabbat+coffee → Israeli culture
    {"word1": "אמא", "word2": "עבודה", "language": "he"},    # mom+work → balance
    {"word1": "חומוס", "word2": "פיצה", "language": "he"},  # hummus+pizza → food
    {"word1": "כסף", "word2": "אהבה", "language": "he"},    # money+love → life
    {"word1": "ילד", "word2": "זקן", "language": "he"},      # child+elder → life cycle
    {"word1": "יום", "word2": "ליל", "language": "he"},      # day+night → time
    {"word1": "חם", "word2": "קר", "language": "he"},        # hot+cold → temperature
    {"word1": "עיר", "word2": "כפר", "language": "he"},      # city+village → settlement
    {"word1": "שיר", "word2": "ריקוד", "language": "he"},    # song+dance → arts
    {"word1": "ספר", "word2": "ילד", "language": "he"},      # book+child → education
    {"word1": "רופא", "word2": "חולה", "language": "he"},    # doctor+patient → health
    {"word1": "אש", "word2": "מים", "language": "he"},        # fire+water → elements
    {"word1": "קרב", "word2": "ניצחון", "language": "he"},  # battle+victory → war
    {"word1": "סרט", "word2": "תיאטרון", "language": "he"}, # film+theater → culture
    # English pairs (all words verified in-vocab)
    {"word1": "ocean", "word2": "mountain", "language": "en"},
    {"word1": "love", "word2": "war", "language": "en"},
    {"word1": "fire", "word2": "ice", "language": "en"},
    {"word1": "morning", "word2": "night", "language": "en"},
    {"word1": "king", "word2": "peasant", "language": "en"},
    {"word1": "silence", "word2": "thunder", "language": "en"},
    {"word1": "city", "word2": "forest", "language": "en"},
    {"word1": "sun", "word2": "moon", "language": "en"},
    {"word1": "past", "word2": "future", "language": "en"},
    {"word1": "cat", "word2": "dog", "language": "en"},
    {"word1": "coffee", "word2": "sleep", "language": "en"},
    {"word1": "gold", "word2": "silver", "language": "en"},
    {"word1": "earth", "word2": "sky", "language": "en"},
    {"word1": "winter", "word2": "summer", "language": "en"},
    {"word1": "soldier", "word2": "peace", "language": "en"},
    {"word1": "child", "word2": "elder", "language": "en"},
]


def get_random_pair(lang: Optional[str] = None) -> Dict:
    if lang:
        filtered = [p for p in STARTING_PAIRS if p["language"] == lang]
        if filtered:
            return random.choice(filtered)
    return random.choice(STARTING_PAIRS)
