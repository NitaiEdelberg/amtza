"""Tests for the curated playable-word list and the endpoint-balance rule.

Both replace judgement that used to live in tuned thresholds, so both are worth
pinning down:

  * the curated list decides *what the computer may answer with at all*, which is
    the difference between offering תבנית and offering ילדה;
  * the balance rule decides whether a word strongly related to both endpoints
    counts as "the middle" or as "too close to one side" — the bug that made
    cat+dog answer "paw" while rejecting "pet".

Run:  cd backend && ./venv/bin/python -m unittest discover -s test -v
"""
import os
import sys
import tempfile
import unittest
from pathlib import Path

import numpy as np

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import embeddings as E  # noqa: E402


def space(words, seed=0):
    """An EmbeddingSpace over random unit vectors — enough for membership tests."""
    rng = np.random.default_rng(seed)
    matrix = rng.standard_normal((len(words), 300)).astype(np.float32)
    matrix /= np.linalg.norm(matrix, axis=1, keepdims=True)
    return E.EmbeddingSpace(
        words=list(words),
        word_to_idx={w: i for i, w in enumerate(words)},
        matrix=matrix.astype(E._STORE_DTYPE),
        nn_index=None,  # unused, but still a required field on the dataclass
        language="he",
    )


class TestCuratedList(unittest.TestCase):
    def setUp(self):
        self._real_data_dir = E.DATA_DIR
        self._tmp = tempfile.TemporaryDirectory()
        E.DATA_DIR = Path(self._tmp.name)
        self.addCleanup(self._tmp.cleanup)
        self.addCleanup(lambda: setattr(E, "DATA_DIR", self._real_data_dir))

    def write_list(self, lang, text):
        (E.DATA_DIR / f"{lang}_playable.txt").write_text(text, encoding="utf-8")

    def test_only_listed_words_are_playable(self):
        vocab = [f"w{i}" for i in range(700)]
        self.write_list("he", "\n".join(vocab[:650]))
        sp = space(vocab)
        mask = E._load_curated_mask(sp, "he")
        self.assertEqual(int(mask.sum()), 650)
        self.assertTrue(mask[sp.word_to_idx["w0"]])
        self.assertFalse(mask[sp.word_to_idx["w699"]])

    def test_comments_blanks_and_multiword_entries_are_ignored(self):
        vocab = [f"w{i}" for i in range(700)] + ["בית", "ספר"]
        listed = ["# a comment", "", "  ", "בית ספר  # can't be an answer: two tokens"]
        listed += vocab[:650]
        self.write_list("he", "\n".join(listed))
        sp = space(vocab)
        mask = E._load_curated_mask(sp, "he")
        self.assertEqual(int(mask.sum()), 650)
        self.assertFalse(mask[sp.word_to_idx["בית"]])

    def test_trailing_comment_on_a_word_line_is_stripped(self):
        vocab = [f"w{i}" for i in range(700)]
        lines = [f"{w}  # note" for w in vocab[:650]]
        self.write_list("he", "\n".join(lines))
        mask = E._load_curated_mask(space(vocab), "he")
        self.assertEqual(int(mask.sum()), 650)

    def test_words_missing_from_the_vocabulary_are_skipped_not_fatal(self):
        vocab = [f"w{i}" for i in range(700)]
        self.write_list("he", "\n".join(vocab[:650] + ["מילה_שלא_קיימת"]))
        mask = E._load_curated_mask(space(vocab), "he")
        self.assertEqual(int(mask.sum()), 650)

    def test_a_truncated_list_falls_back_instead_of_crippling_the_pool(self):
        # A list that matched almost nothing would leave the computer with a
        # handful of answers for the whole semantic space. Better to fall back.
        vocab = [f"w{i}" for i in range(700)]
        self.write_list("he", "\n".join(vocab[:5]))
        self.assertIsNone(E._load_curated_mask(space(vocab), "he"))

    def test_no_file_means_no_curated_mask(self):
        self.assertIsNone(E._load_curated_mask(space([f"w{i}" for i in range(700)]), "he"))

    def test_the_shipped_lists_parse_and_are_substantial(self):
        for lang in ("he", "en"):
            path = self._real_data_dir / f"{lang}_playable.txt"
            self.assertTrue(path.exists(), f"missing {path}")
            words = [
                line.split("#", 1)[0].strip()
                for line in path.read_text(encoding="utf-8").splitlines()
            ]
            words = [w for w in words if w and " " not in w]
            self.assertGreater(len(words), E._MIN_CURATED_WORDS,
                               f"{lang} list is below the fallback threshold")


class TestEndpointBalance(unittest.TestCase):
    """max(s1, s2) above the ceiling only disqualifies a *lopsided* candidate."""

    def test_a_word_close_to_both_ends_is_kept(self):
        # "pet" for cat+dog: 0.68 / 0.73 — over the ceiling, but even-handed.
        self.assertFalse(E._too_close_to_one_end(0.68, 0.73, 0.58))

    def test_a_word_glued_to_one_end_is_rejected(self):
        # "kitten" for cat+dog: 0.81 / 0.61.
        self.assertTrue(E._too_close_to_one_end(0.81, 0.61, 0.58))
        # "sea" for ocean+mountain: 0.78 / 0.44.
        self.assertTrue(E._too_close_to_one_end(0.78, 0.44, 0.58))

    def test_it_is_symmetric_in_its_arguments(self):
        for a, b in ((0.81, 0.61), (0.68, 0.73), (0.30, 0.90)):
            self.assertEqual(
                E._too_close_to_one_end(a, b, 0.58),
                E._too_close_to_one_end(b, a, 0.58),
            )

    def test_nothing_below_the_ceiling_is_ever_rejected(self):
        # However lopsided, a candidate under the ceiling is the floor's problem.
        self.assertFalse(E._too_close_to_one_end(0.57, 0.10, 0.58))

    def test_the_tolerance_sits_between_the_measured_populations(self):
        balanced = [0.01, 0.03, 0.06]      # autumn, evening, pet
        lopsided = [0.20, 0.21, 0.30, 0.33]  # kitten, afternoon, valley, sea
        self.assertGreater(E._IMBALANCE_TOL, max(balanced))
        self.assertLess(E._IMBALANCE_TOL, min(lopsided))


if __name__ == "__main__":
    unittest.main()
