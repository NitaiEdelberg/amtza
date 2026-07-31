"""User-experience tests: the parts a player actually touches on every game.

These need no fastText models — they cover the curated starting pairs (what the
player sees first) and input normalization (whether the word a player *types* is
recognized: Hebrew niqqud, casing, multi-word phrases).

Run:  cd backend && ./venv/bin/python -m unittest discover -s test -v
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from word_pairs import STARTING_PAIRS, get_random_pair  # noqa: E402
from embeddings import normalize_word, detect_language  # noqa: E402


class TestStartingPairs(unittest.TestCase):
    def test_every_pair_is_well_formed(self):
        # A malformed starting pair means the very first screen of a game breaks.
        for p in STARTING_PAIRS:
            self.assertIn("word1", p)
            self.assertIn("word2", p)
            self.assertIn(p["language"], ("he", "en"))
            self.assertTrue(p["word1"].strip(), f"empty word1 in {p}")
            self.assertTrue(p["word2"].strip(), f"empty word2 in {p}")
            self.assertNotEqual(
                p["word1"], p["word2"], f"a pair must be two different words: {p}"
            )

    def test_pair_language_matches_its_words(self):
        # A Hebrew pair whose words aren't Hebrew (or vice-versa) would route the
        # guess to the wrong embedding space and never validate.
        for p in STARTING_PAIRS:
            self.assertEqual(detect_language(p["word1"]), p["language"], f"lang mismatch: {p}")
            self.assertEqual(detect_language(p["word2"]), p["language"], f"lang mismatch: {p}")

    def test_get_random_pair_respects_language(self):
        for _ in range(50):
            self.assertEqual(get_random_pair("he")["language"], "he")
            self.assertEqual(get_random_pair("en")["language"], "en")

    def test_get_random_pair_unknown_language_falls_back(self):
        # An unexpected lang code must not crash — it just returns some pair.
        p = get_random_pair("fr")
        self.assertIn(p["language"], ("he", "en"))

    def test_get_random_pair_default_returns_a_valid_pair(self):
        p = get_random_pair(None)
        self.assertIn("word1", p)
        self.assertIn(p["language"], ("he", "en"))

    def test_both_languages_are_represented(self):
        langs = {p["language"] for p in STARTING_PAIRS}
        self.assertEqual(langs, {"he", "en"})


class TestNormalizeWord(unittest.TestCase):
    def test_english_is_lowercased(self):
        self.assertEqual(normalize_word("OCEAN", "en"), "ocean")
        self.assertEqual(normalize_word("  Mountain ", "en"), "mountain")

    def test_hebrew_niqqud_is_stripped(self):
        # A player who types with vowel points should still match the bare word.
        with_niqqud = "שָׁלוֹם"
        self.assertEqual(normalize_word(with_niqqud, "he"), "שלום")

    def test_hebrew_makaf_is_stripped(self):
        # The Hebrew hyphen (maqaf) is removed so "בית־ספר" → "ביתספר" isn't split oddly.
        self.assertEqual(normalize_word("תל־אביב", "he"), "תלאביב")

    def test_multiword_phrase_keeps_its_space(self):
        # main.py relies on this so "תל אביב" stays a phrase rather than one token.
        self.assertEqual(normalize_word("תל אביב", "he"), "תל אביב")

    def test_surrounding_whitespace_trimmed(self):
        self.assertEqual(normalize_word("  ירח  ", "he"), "ירח")


class TestDetectLanguage(unittest.TestCase):
    def test_hebrew_detected(self):
        self.assertEqual(detect_language("שלום"), "he")

    def test_english_detected(self):
        self.assertEqual(detect_language("hello"), "en")

    def test_mixed_leads_with_hebrew(self):
        # Any Hebrew character present routes to the Hebrew space.
        self.assertEqual(detect_language("shalom שלום"), "he")


if __name__ == "__main__":
    unittest.main()
