"""Tests for what counts as a playable guess.

is_valid_word is the gate both /validate and /guess use. It has to agree with
itself: /guess used to skip it entirely, which made "12345" a playable guess —
Common Crawl carries that token, so it has a vector despite not being a word.

Uses a small fake vocabulary, so no models are needed.
"""
import os
import sys
import unittest

import numpy as np

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from embeddings import EmbeddingSpace, is_valid_word  # noqa: E402


def fake_space(words, language="en"):
    return EmbeddingSpace(
        words=list(words),
        word_to_idx={w: i for i, w in enumerate(words)},
        matrix=np.zeros((len(words), 2), dtype=np.float32),
        nn_index=None,
        language=language,
    )


EN = fake_space(["fire", "ice", "steam", "12345", "new", "york", "well-known"], "en")
HE = fake_space(["שבת", "קפה", "בוקר", "תל", "אביב"], "he")


class TestEnglishGuesses(unittest.TestCase):
    def test_a_real_word_is_accepted(self):
        self.assertTrue(is_valid_word(EN, "steam"))

    def test_case_is_ignored(self):
        self.assertTrue(is_valid_word(EN, "STEAM"))

    def test_pure_digits_are_rejected_even_though_the_token_exists(self):
        # "12345" is in the vocabulary and has a vector; it still isn't a word.
        self.assertIn("12345", EN.word_to_idx)
        self.assertFalse(is_valid_word(EN, "12345"))

    def test_letters_mixed_with_digits_are_rejected(self):
        self.assertFalse(is_valid_word(EN, "fire2"))

    def test_symbols_are_rejected(self):
        self.assertFalse(is_valid_word(EN, "!@#$%"))

    def test_empty_and_whitespace_are_rejected(self):
        self.assertFalse(is_valid_word(EN, ""))
        self.assertFalse(is_valid_word(EN, "   "))

    def test_unknown_word_is_rejected(self):
        self.assertFalse(is_valid_word(EN, "zzzqqq"))

    def test_hyphens_and_apostrophes_are_allowed(self):
        self.assertTrue(is_valid_word(EN, "well-known"))

    def test_multi_word_phrase_passes_if_one_token_is_known(self):
        self.assertTrue(is_valid_word(EN, "new york"))

    def test_absurdly_long_input_is_rejected(self):
        self.assertFalse(is_valid_word(EN, "a" * 60))


class TestHebrewGuesses(unittest.TestCase):
    def test_a_real_word_is_accepted(self):
        self.assertTrue(is_valid_word(HE, "בוקר"))

    def test_latin_letters_are_rejected(self):
        self.assertFalse(is_valid_word(HE, "shalom"))

    def test_digits_are_rejected(self):
        self.assertFalse(is_valid_word(HE, "12345"))

    def test_multi_word_hebrew_phrase_is_accepted(self):
        self.assertTrue(is_valid_word(HE, "תל אביב"))

    def test_niqqud_is_tolerated(self):
        # Vowel points are stripped before the vocabulary check.
        self.assertTrue(is_valid_word(HE, "בּוֹקֶר"))

    def test_words_outside_the_vocabulary_are_still_allowed(self):
        # Deliberate: the Hebrew model has real gaps, and a spurious rejection of a
        # genuine word is worse than letting /guess answer with a suggestion.
        self.assertTrue(is_valid_word(HE, "מילהחדשה"))


if __name__ == "__main__":
    unittest.main()
