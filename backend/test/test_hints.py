"""Tests for the hint feature's core promise: a hint must not be the answer.

Built on a small synthetic embedding space with a stubbed nearest-neighbour index,
so it runs without the real 140k-word models.

Run:  cd backend && ./venv/bin/python -m unittest discover -s test -v
"""
import os
import sys
import unittest

import numpy as np

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import embeddings  # noqa: E402
from embeddings import EmbeddingSpace, get_hints  # noqa: E402


class StubIndex:
    """Returns the given neighbour order regardless of the query vector."""

    def __init__(self, order):
        self.order = order

    def kneighbors(self, _query, n_neighbors):
        return None, np.array([self.order[:n_neighbors]])


def make_space(words, neighbour_order=None):
    n = len(words)
    # Distinct unit vectors; the stub index decides ordering, not geometry.
    matrix = np.eye(n, dtype=np.float32)
    order = neighbour_order if neighbour_order is not None else list(range(n))
    return EmbeddingSpace(
        words=list(words),
        word_to_idx={w: i for i, w in enumerate(words)},
        matrix=matrix,
        nn_index=StubIndex(order),
        language="en",
        good_mask=np.ones(n, dtype=bool),
    )


WORDS = [
    "fire", "ice",                                    # the pair
    "n1", "n2", "n3", "n4",                           # the first four, skipped
    "answer",                                          # what the computer would play
    "h1", "h2", "h3", "h4", "h5",                     # hint candidates
]


class TestHintsDoNotLeakTheAnswer(unittest.TestCase):
    def setUp(self):
        self._real_find = embeddings.find_best_middle
        # The computer's pick lands inside the hint band — the exact situation
        # measured on 7 of 33 real starting pairs.
        embeddings.find_best_middle = lambda space, w1, w2, exclude: "answer"

    def tearDown(self):
        embeddings.find_best_middle = self._real_find

    def test_answer_is_never_offered_as_a_hint(self):
        space = make_space(WORDS)
        hints = get_hints(space, "fire", "ice")
        self.assertNotIn("answer", hints)

    def test_returns_the_requested_number_of_hints(self):
        space = make_space(WORDS)
        self.assertEqual(len(get_hints(space, "fire", "ice")), 3)

    def test_hints_exclude_the_pair_words_themselves(self):
        space = make_space(WORDS)
        hints = get_hints(space, "fire", "ice")
        self.assertNotIn("fire", hints)
        self.assertNotIn("ice", hints)

    def test_hints_are_distinct(self):
        space = make_space(WORDS)
        hints = get_hints(space, "fire", "ice")
        self.assertEqual(len(hints), len(set(hints)))

    def test_survives_a_pair_with_no_computer_answer(self):
        # find_best_middle can return None when everything nearby is excluded;
        # hints should still come back rather than raising.
        embeddings.find_best_middle = lambda space, w1, w2, exclude: None
        space = make_space(WORDS)
        self.assertEqual(len(get_hints(space, "fire", "ice")), 3)

    def test_respects_n_hints(self):
        space = make_space(WORDS)
        self.assertEqual(len(get_hints(space, "fire", "ice", n_hints=2)), 2)

    def test_skips_words_failing_the_quality_filter(self):
        space = make_space(WORDS)
        blocked = space.word_to_idx["h1"]
        space.good_mask[blocked] = False
        self.assertNotIn("h1", get_hints(space, "fire", "ice"))


if __name__ == "__main__":
    unittest.main()
