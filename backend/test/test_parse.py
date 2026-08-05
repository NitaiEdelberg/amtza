"""Tests for parsing a fastText .vec stream into an embedding matrix.

This routine was rewritten to survive a 512MB container: it fills one
preallocated float16 buffer and normalises each row inline, instead of
accumulating a list of float32 arrays and calling np.vstack. That is easy to get
subtly wrong — an off-by-one on the write cursor, a row left un-normalised, or a
word list that no longer lines up with its matrix row — and none of those would
raise. They would just make the game quietly pick worse words.

So: assert the contract, not the implementation.

Run:  cd backend && ./venv/bin/python -m unittest discover -s test -v
"""
import io
import os
import sys
import unittest

import numpy as np

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import embeddings as E  # noqa: E402


def vec_stream(rows, dim=300):
    """A .vec text stream: a "N dim" header, then "word v1 v2 ... vdim" per line."""
    lines = [f"{len(rows)} {dim}"]
    for word, vals in rows:
        lines.append(word + " " + " ".join(f"{v:.6f}" for v in vals))
    return io.StringIO("\n".join(lines) + "\n")


def row(seed, dim=300, scale=1.0):
    rng = np.random.default_rng(seed)
    return (rng.standard_normal(dim) * scale).tolist()


class TestParseContract(unittest.TestCase):
    def test_words_and_matrix_stay_aligned(self):
        rows = [("alpha", row(1)), ("beta", row(2)), ("gamma", row(3))]
        words, matrix = E._parse_vec_stream(vec_stream(rows), max_words=10, language="en")
        self.assertEqual(words, ["alpha", "beta", "gamma"])
        self.assertEqual(matrix.shape, (3, 300))

    def test_matrix_is_stored_at_half_precision(self):
        words, matrix = E._parse_vec_stream(
            vec_stream([("alpha", row(1))]), max_words=10, language="en")
        self.assertEqual(matrix.dtype, E._STORE_DTYPE)

    def test_every_row_is_l2_normalised(self):
        # Deliberately varied magnitudes: normalisation must be per row, not global.
        rows = [("a", row(1, scale=0.01)), ("b", row(2, scale=1.0)), ("c", row(3, scale=100.0))]
        _, matrix = E._parse_vec_stream(vec_stream(rows), max_words=10, language="en")
        norms = np.linalg.norm(matrix.astype(np.float32), axis=1)
        np.testing.assert_allclose(norms, 1.0, atol=1e-3)

    def test_direction_is_preserved_through_the_downcast(self):
        # The whole game is cosine similarity, so what must survive float16 is the
        # angle. Compare against the float32 result computed independently.
        raw = row(7)
        _, matrix = E._parse_vec_stream(
            vec_stream([("w", raw)]), max_words=10, language="en")
        expected = np.array(raw, dtype=np.float32)
        expected /= np.linalg.norm(expected)
        cosine = float(np.dot(matrix[0].astype(np.float32), expected))
        self.assertGreater(cosine, 0.9999)

    def test_a_zero_vector_does_not_produce_nan(self):
        # A degenerate row must not poison every later similarity with NaN.
        _, matrix = E._parse_vec_stream(
            vec_stream([("zero", [0.0] * 300)]), max_words=10, language="en")
        self.assertFalse(np.isnan(matrix.astype(np.float32)).any())

    def test_max_words_caps_the_result(self):
        rows = [(f"w{i}", row(i)) for i in range(20)]
        words, matrix = E._parse_vec_stream(vec_stream(rows), max_words=5, language="en")
        self.assertEqual(len(words), 5)
        self.assertEqual(matrix.shape[0], 5)

    def test_short_lines_are_skipped_without_shifting_rows(self):
        # A truncated line must not leave a stale/blank row behind: the surviving
        # words have to map to their own vectors, which is what the cosine checks.
        good_a, good_b = row(11), row(12)
        stream = io.StringIO(
            "3 300\n"
            + "alpha " + " ".join(f"{v:.6f}" for v in good_a) + "\n"
            + "truncated 1.0 2.0 3.0\n"
            + "gamma " + " ".join(f"{v:.6f}" for v in good_b) + "\n"
        )
        words, matrix = E._parse_vec_stream(stream, max_words=10, language="en")
        self.assertEqual(words, ["alpha", "gamma"])
        for i, raw in enumerate((good_a, good_b)):
            expected = np.array(raw, dtype=np.float32)
            expected /= np.linalg.norm(expected)
            self.assertGreater(float(np.dot(matrix[i].astype(np.float32), expected)), 0.9999)


class TestHebrewFiltering(unittest.TestCase):
    def test_suffix_possessive_forms_are_dropped_with_their_rows(self):
        # זעמו is זעם + possessive ו, and its base is present, so it goes. The rows
        # that remain must still belong to the words that remain.
        rows = [("זעם", row(1)), ("זעמו", row(2)), ("שלום", row(3))]
        words, matrix = E._parse_vec_stream(vec_stream(rows), max_words=10, language="he")
        self.assertNotIn("זעמו", words)
        self.assertEqual(words, ["זעם", "שלום"])
        self.assertEqual(matrix.shape[0], 2)

        expected = np.array(rows[2][1], dtype=np.float32)
        expected /= np.linalg.norm(expected)
        cosine = float(np.dot(matrix[words.index("שלום")].astype(np.float32), expected))
        self.assertGreater(cosine, 0.9999, "שלום kept the row belonging to זעמו")

    def test_english_is_not_filtered(self):
        rows = [("go", row(1)), ("goes", row(2))]
        words, _ = E._parse_vec_stream(vec_stream(rows), max_words=10, language="en")
        self.assertEqual(words, ["go", "goes"])


class TestSimilarityHelpers(unittest.TestCase):
    """_sims_all must match a plain float32 matmul; it exists only to bound memory."""

    def _space(self, matrix):
        words = [f"w{i}" for i in range(matrix.shape[0])]
        return E.EmbeddingSpace(
            words=words, word_to_idx={w: i for i, w in enumerate(words)},
            matrix=matrix, nn_index=None, language="en")

    def test_chunked_matmul_matches_the_direct_one(self):
        rng = np.random.default_rng(3)
        m = rng.standard_normal((5000, 300)).astype(np.float32)
        m /= np.linalg.norm(m, axis=1, keepdims=True)
        vec = m[7].copy()

        direct = m @ vec
        chunked = E._sims_all(self._space(m.astype(E._STORE_DTYPE)), vec)
        # float16 storage, float32 accumulation: agreement to ~1e-3 is the design.
        np.testing.assert_allclose(chunked, direct, atol=2e-3)

    def test_it_spans_every_chunk_boundary(self):
        # A vocabulary larger than one slice would silently return zeros for the
        # tail if the loop bounds were wrong.
        rng = np.random.default_rng(4)
        n = E._SIM_CHUNK * 2 + 17
        m = rng.standard_normal((n, 300)).astype(np.float32)
        m /= np.linalg.norm(m, axis=1, keepdims=True)
        sims = E._sims_all(self._space(m.astype(E._STORE_DTYPE)), m[-1].copy())
        self.assertEqual(sims.shape, (n,))
        self.assertGreater(float(sims[-1]), 0.99, "last row should match itself")
        self.assertFalse(np.all(sims[E._SIM_CHUNK:] == 0))

    def test_float32_matrices_still_work(self):
        # Test fixtures elsewhere build float32 spaces directly.
        rng = np.random.default_rng(5)
        m = rng.standard_normal((100, 300)).astype(np.float32)
        m /= np.linalg.norm(m, axis=1, keepdims=True)
        np.testing.assert_allclose(E._sims_all(self._space(m), m[0]), m @ m[0], atol=1e-6)

    def test_row_reads_return_float32(self):
        # _row exists so np.dot never accumulates 300 terms in half precision.
        m = np.eye(4, 300, dtype=E._STORE_DTYPE)
        self.assertEqual(E._row(self._space(m), 2).dtype, np.float32)


if __name__ == "__main__":
    unittest.main()
