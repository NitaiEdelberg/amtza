"""The middle-vector path (middle_vectors.py): when it decides, and when it steps aside.

Uses a tiny hand-made table, so it runs without the real 17MB file.

Run:  cd backend && ./venv/bin/python -m unittest discover -s test -v
"""
import os
import sys
import unittest

import numpy as np

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import associations  # noqa: E402
import embeddings as E  # noqa: E402
import middle_vectors as M  # noqa: E402


def space_with(words, language="he"):
    rng = np.random.default_rng(0)
    m = rng.normal(size=(len(words), 8)).astype(np.float32)
    m /= np.linalg.norm(m, axis=1, keepdims=True)
    s = E.EmbeddingSpace(words=list(words), word_to_idx={w: i for i, w in enumerate(words)},
                         matrix=m, nn_index=None, language=language,
                         good_mask=np.array([w not in ("עץ", "תפוח", "x") for w in words]))
    E._build_good_submatrix(s)
    return s


def table_for(vectors):
    """vectors: {word: 3-d direction}; both sources get the same direction."""
    words = list(vectors)
    v = np.array([vectors[w] for w in words], dtype=np.float32)
    v /= np.linalg.norm(v, axis=1, keepdims=True)
    q = np.round(v * 127).astype(np.int8)
    return M.MiddleTable(words, q, q)


WORDS = ["עץ", "תפוח", "פרי", "תאנה", "שולחן", "פריים"]
# In the table "fruit" sits between tree and apple; "fig" leans to apple.
VECS = {"עץ": [1, 0, 0], "תפוח": [0, 1, 0], "פרי": [1, 1, 0.1],
        "תאנה": [0.2, 1, 0.3], "שולחן": [0, 0, 1], "פריים": [1, 1, 0.5]}


class WithTable(unittest.TestCase):
    def setUp(self):
        self._m, self._a = dict(M._cache), dict(associations._cache)
        M._cache.clear()
        associations._cache.clear()
        M._cache["he"] = table_for(VECS)
        associations._cache["he"] = None
        self.space = space_with(WORDS)
        # The fake space's old vectors are random, so the old-vector guard is
        # off here and tested on its own below.
        self._floor = E.MIDDLE_OLD_FLOOR
        E.MIDDLE_OLD_FLOOR = 0.0

    def tearDown(self):
        E.MIDDLE_OLD_FLOOR = self._floor
        M._cache.clear(); M._cache.update(self._m)
        associations._cache.clear(); associations._cache.update(self._a)

    def pick(self, w1="עץ", w2="תפוח", extra=()):
        ex = {w1, w2} | set(extra)
        return E.find_best_middle(self.space, w1, w2, ex)

    def test_the_table_decides_when_both_words_are_in_it(self):
        self.assertEqual(self.pick(), "פרי")

    def test_used_words_are_still_excluded(self):
        self.assertNotIn(self.pick(extra={"פרי"}), {"פרי"})

    def test_a_recycled_form_of_a_used_word_is_skipped(self):
        # "פריים" contains the used "פרי": the old path's rule still applies.
        self.assertNotIn(self.pick(extra={"פרי"}), {"פרי", "פריים"})

    def test_a_board_word_missing_from_the_table_falls_back_to_the_old_path(self):
        space = space_with(WORDS + ["x"])
        self.assertIsNone(E._middle_from_table(space, "x", "תפוח", {"x", "תפוח"}))
        self.assertIsNotNone(E.find_best_middle(space, "x", "תפוח", {"x", "תפוח"}))

    def test_the_old_vectors_can_veto_a_pick_they_call_unrelated(self):
        E.MIDDLE_OLD_FLOOR = 0.999   # nothing is that close under random vectors
        self.assertIsNone(E._middle_from_table(self.space, "עץ", "תפוח", {"עץ", "תפוח"}))

    def test_typed_geresh_variants_find_the_same_row(self):
        t = table_for({"ז'אנר": [1, 0, 0]})
        self.assertIsNotNone(t.query("ז׳אנר"))
        self.assertIsNotNone(t.query("ז’אנר"))


class WithoutTable(unittest.TestCase):
    def test_a_language_without_a_table_is_untouched(self):
        saved = dict(M._cache)
        M._cache["en"] = None
        try:
            s = space_with(["a", "b", "c", "d"], language="en")
            self.assertIsNone(E._middle_from_table(s, "a", "b", {"a", "b"}))
        finally:
            M._cache.clear(); M._cache.update(saved)


if __name__ == "__main__":
    unittest.main()
