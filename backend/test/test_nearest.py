"""Tests for _nearest_indices, the matmul-based nearest-neighbour search.

It replaced a scikit-learn NearestNeighbors cosine query (30x faster once the
Hebrew vocabulary reached ~140k words), so what matters is that it returns the
same thing: the n closest rows, closest first.

Run:  cd backend && ./venv/bin/python -m unittest discover -s test -v
"""
import os
import sys
import unittest

import numpy as np

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from embeddings import EmbeddingSpace, _nearest_indices  # noqa: E402


def random_space(n=500, dim=16, seed=0):
    """A space of random L2-normalised rows — the invariant the search relies on."""
    rng = np.random.default_rng(seed)
    m = rng.normal(size=(n, dim)).astype(np.float32)
    m /= np.linalg.norm(m, axis=1, keepdims=True)
    return EmbeddingSpace(
        words=[f"w{i}" for i in range(n)],
        word_to_idx={f"w{i}": i for i in range(n)},
        matrix=m,
        nn_index=None,
        language="en",
    )


def brute_force(space, vec, n):
    """Reference ranking: every cosine, sorted descending."""
    sims = space.matrix @ vec
    return list(np.argsort(-sims)[:n])


class TestNearestIndices(unittest.TestCase):
    def setUp(self):
        self.space = random_space()
        self.query = self.space.matrix[7]  # an actual row, so rank 1 is itself

    def test_matches_a_brute_force_ranking(self):
        for n in (1, 5, 50, 200):
            got = list(_nearest_indices(self.space, self.query, n))
            self.assertEqual(got, brute_force(self.space, self.query, n), f"n={n}")

    def test_query_row_ranks_first(self):
        self.assertEqual(_nearest_indices(self.space, self.query, 5)[0], 7)

    def test_results_are_sorted_by_descending_similarity(self):
        idx = _nearest_indices(self.space, self.query, 40)
        sims = self.space.matrix[idx] @ self.query
        self.assertTrue(np.all(np.diff(sims) <= 1e-6), "similarities must not increase")

    def test_returns_exactly_n_indices(self):
        self.assertEqual(len(_nearest_indices(self.space, self.query, 33)), 33)

    def test_n_larger_than_vocabulary_is_clamped(self):
        n = len(self.space.words)
        self.assertEqual(len(_nearest_indices(self.space, self.query, n + 500)), n)

    def test_handles_a_single_word_space(self):
        space = random_space(n=1)
        self.assertEqual(list(_nearest_indices(space, space.matrix[0], 5)), [0])

    def test_indices_are_unique(self):
        idx = list(_nearest_indices(self.space, self.query, 100))
        self.assertEqual(len(idx), len(set(idx)))


if __name__ == "__main__":
    unittest.main()
