"""Rules about what the computer may say and which player words resolve.

Both came out of a play-test: the computer recycled words already on the board
(גיבור -> גיבורה, מחזמר -> זמר), and loanwords typed with a geresh (ז'אנר) were
rejected as unknown because the corpus split them at the apostrophe.

Run:  cd backend && ./venv/bin/python -m unittest discover -s test -v
"""
import os
import sys
import unittest

import numpy as np

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import associations  # noqa: E402
from embeddings import (  # noqa: E402
    EmbeddingSpace, _is_derived_form, find_best_middle, get_word_vector, lookup_index,
)


def make_space(words, vectors, language):
    m = np.asarray(vectors, dtype=np.float32)
    m /= np.linalg.norm(m, axis=1, keepdims=True)
    return EmbeddingSpace(
        words=list(words), word_to_idx={w: i for i, w in enumerate(words)},
        matrix=m, nn_index=None, language=language,
        good_mask=np.ones(len(words), dtype=bool),
    )


class WithoutRealAssociations(unittest.TestCase):
    """Fake vocabularies must not meet the real association files."""

    def setUp(self):
        self._saved = dict(associations._cache)
        associations._cache.clear()
        associations._cache.update({"he": None, "en": None})

    def tearDown(self):
        associations._cache.clear()
        associations._cache.update(self._saved)


class TestDerivedForms(WithoutRealAssociations):
    def test_hebrew_inflections_and_cut_words_are_derived(self):
        for word, played in [("גיבורה", "גיבור"), ("שחקנית", "שחקן"), ("זמר", "מחזמר"),
                             ("ציפורן", "ציפור"), ("שמח", "שמחה")]:
            with self.subTest(word=word):
                self.assertTrue(_is_derived_form(word, {played}, "he"))

    def test_short_hebrew_coincidences_are_not(self):
        # ים inside מים is spelling, not derivation.
        self.assertFalse(_is_derived_form("מים", {"ים"}, "he"))

    def test_unrelated_hebrew_words_are_not(self):
        self.assertFalse(_is_derived_form("תאורה", {"מוזיקה"}, "he"))

    def test_english_uses_prefixes_not_substrings(self):
        self.assertTrue(_is_derived_form("wheel", {"wheels"}, "en"))
        self.assertTrue(_is_derived_form("writer", {"write"}, "en"))
        self.assertFalse(_is_derived_form("party", {"art"}, "en"))

    def test_computer_skips_a_derived_form_even_when_it_scores_best(self):
        # "heroine" sits exactly between the pair; "legend" is a little weaker.
        words = ["hero", "movie", "heroine", "legend"]
        vecs = [[1, 0, 0], [0, 1, 0], [1, 1, 0.1], [1, 1, 0.6]]
        space = make_space(words, vecs, "en")
        self.assertEqual(find_best_middle(space, "hero", "movie", {"hero", "movie"}), "legend")


class TestAssociationBonus(WithoutRealAssociations):
    # "fruit" is the human answer for apple+tree but sits further from both than
    # "fig" does, which is exactly how the vectors get this wrong.
    WORDS = ["apple", "tree", "fig", "fruit"]
    VECS = [[1, 0, 0], [0, 1, 0], [1, 1, 0.2], [1, 1, 1.0]]

    def test_without_associations_the_closer_sibling_wins(self):
        space = make_space(self.WORDS, self.VECS, "en")
        self.assertEqual(find_best_middle(space, "apple", "tree", {"apple", "tree"}), "fig")

    def test_a_word_people_link_to_both_sides_wins(self):
        associations._cache["en"] = associations.Associations(
            {"fruit": associations._weights([], ["apple", "tree"])}, "en")
        space = make_space(self.WORDS, self.VECS, "en")
        self.assertEqual(find_best_middle(space, "apple", "tree", {"apple", "tree"}), "fruit")

    def test_links_are_found_from_either_side_and_through_plurals(self):
        a = associations.Associations({"apple": associations._weights(["fruit"], [])}, "en")
        self.assertGreater(a.link("fruit", "apples"), 0)   # reverse link, plural on board
        self.assertEqual(a.link("fruit", "tree"), 0)


class TestGereshAliases(unittest.TestCase):
    def setUp(self):
        self.space = make_space(["אנר", "סוגה", "חנון"], np.eye(3), "he")

    def test_listed_loanword_resolves_with_any_apostrophe(self):
        for typed in ("ז'אנר", "ז׳אנר", "ז’אנר"):
            with self.subTest(typed=typed):
                self.assertEqual(lookup_index(self.space, typed), 0)
                self.assertIsNotNone(get_word_vector(self.space, typed))

    def test_unlisted_loanword_does_not_fall_back_to_its_fragment(self):
        # ג'חנון -> "חנון" means "nerd"; only checked entries may resolve.
        self.assertIsNone(lookup_index(self.space, "ג'חנון"))

    def test_aliases_are_hebrew_only(self):
        en = make_space(["anr"], np.eye(1), "en")
        self.assertIsNone(lookup_index(en, "ז'אנר"))


if __name__ == "__main__":
    unittest.main()
