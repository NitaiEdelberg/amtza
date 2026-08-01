"""Tests for the 'did you mean' engine that rescues a rejected guess.

Uses a small fake vocabulary rather than the real 140k-word model, so these run in
milliseconds with no model files.

Run:  cd backend && ./venv/bin/python -m unittest discover -s test -v
"""
import os
import sys
import unittest

import numpy as np

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from embeddings import (  # noqa: E402
    EmbeddingSpace,
    _edit_distance_within_1,
    _spelling_variants,
    suggest_similar,
)


def fake_space(words, language="he"):
    """A minimal EmbeddingSpace: suggest_similar only needs words + word_to_idx.

    Word order matters — it encodes corpus frequency, which is how suggestions
    are ranked.
    """
    return EmbeddingSpace(
        words=list(words),
        word_to_idx={w: i for i, w in enumerate(words)},
        matrix=np.zeros((len(words), 2), dtype=np.float32),
        nn_index=None,
        language=language,
    )


class TestEditDistance(unittest.TestCase):
    def test_identical(self):
        self.assertTrue(_edit_distance_within_1("cat", "cat"))

    def test_single_substitution(self):
        self.assertTrue(_edit_distance_within_1("cat", "cut"))

    def test_single_insertion_either_direction(self):
        self.assertTrue(_edit_distance_within_1("cat", "cart"))
        self.assertTrue(_edit_distance_within_1("cart", "cat"))

    def test_two_edits_rejected(self):
        self.assertFalse(_edit_distance_within_1("cat", "dog"))
        self.assertFalse(_edit_distance_within_1("cat", "cars"))

    def test_length_gap_over_one_rejected(self):
        self.assertFalse(_edit_distance_within_1("cat", "catty"))


class TestSpellingVariants(unittest.TestCase):
    def test_drops_optional_vowel_letters(self):
        # בוקר -> בקר : Hebrew writes ו optionally (ktiv male vs haser).
        self.assertIn("בקר", _spelling_variants("בוקר"))

    def test_adds_optional_vowel_letters(self):
        # שלחן -> שולחן
        self.assertIn("שולחן", _spelling_variants("שלחן"))

    def test_never_returns_the_input_itself(self):
        self.assertNotIn("בוקר", _spelling_variants("בוקר"))


class TestSuggestSimilar(unittest.TestCase):
    def test_finds_the_full_spelling(self):
        space = fake_space(["שולחן", "כיסא", "בוקר"])
        self.assertEqual(suggest_similar(space, "שלחן")[0], "שולחן")

    def test_finds_the_defective_spelling(self):
        space = fake_space(["בקר", "ערב"])
        self.assertEqual(suggest_similar(space, "בוקר")[0], "בקר")

    def test_finds_the_final_letter_form(self):
        # A player typing a medial letter where the corpus stores the final form.
        space = fake_space(["חלון", "מלך"])
        self.assertEqual(suggest_similar(space, "חלונ")[0], "חלון")
        self.assertEqual(suggest_similar(space, "מלכ")[0], "מלך")

    def test_ranks_by_corpus_frequency(self):
        # Both are one edit away; the earlier (more frequent) word wins.
        space = fake_space(["תפוח", "תפוחי"])
        self.assertEqual(suggest_similar(space, "תפוחח")[0], "תפוח")

    def test_never_suggests_the_word_itself(self):
        space = fake_space(["ילדה", "ילד"])
        self.assertNotIn("ילדה", suggest_similar(space, "ילדה"))

    def test_english_typo_falls_back_to_edit_distance(self):
        space = fake_space(["mountain", "ocean", "coffee"], language="en")
        self.assertEqual(suggest_similar(space, "montain"), ["mountain"])

    def test_respects_the_limit(self):
        space = fake_space(["תפוח", "תפוחי", "תפוחים", "תפוז"])
        self.assertLessEqual(len(suggest_similar(space, "תפוחח", limit=2)), 2)

    def test_no_match_returns_empty(self):
        space = fake_space(["ocean", "mountain"], language="en")
        self.assertEqual(suggest_similar(space, "zzzzzzzz"), [])

    def test_empty_input_is_safe(self):
        space = fake_space(["ocean"], language="en")
        self.assertEqual(suggest_similar(space, "   "), [])


if __name__ == "__main__":
    unittest.main()
