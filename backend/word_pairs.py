import random

STARTING_PAIRS = [
    # Hebrew cultural pairs
    {"word1": "חביתה", "word2": "בן גוריון", "language": "he"},
    {"word1": "ים", "word2": "מדבר", "language": "he"},
    {"word1": "שבת", "word2": "קפה", "language": "he"},
    {"word1": "אמא", "word2": "עבודה", "language": "he"},
    {"word1": "תל אביב", "word2": "ירושלים", "language": "he"},
    {"word1": "חומוס", "word2": "פיצה", "language": "he"},
    {"word1": "חייל", "word2": "שלום", "language": "he"},
    {"word1": "כסף", "word2": "אהבה", "language": "he"},
    {"word1": "שמש", "word2": "ירח", "language": "he"},
    {"word1": "מלך", "word2": "עם", "language": "he"},
    {"word1": "ילד", "word2": "זקן", "language": "he"},
    {"word1": "יום", "word2": "לילה", "language": "he"},
    {"word1": "רעב", "word2": "שבע", "language": "he"},
    {"word1": "חם", "word2": "קר", "language": "he"},
    {"word1": "עיר", "word2": "כפר", "language": "he"},
    # English pairs
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
    {"word1": "rich", "word2": "poor", "language": "en"},
    {"word1": "fast", "word2": "slow", "language": "en"},
    {"word1": "earth", "word2": "sky", "language": "en"},
    {"word1": "winter", "word2": "summer", "language": "en"},
]


def get_random_pair(lang: str | None = None) -> dict:
    if lang:
        filtered = [p for p in STARTING_PAIRS if p["language"] == lang]
        if filtered:
            return random.choice(filtered)
    return random.choice(STARTING_PAIRS)
