"""/guess refuses what the screen refuses.

Calls the endpoint function directly on a tiny fake vocabulary; every check here
runs before any vector maths, so no models are needed.

Run:  cd backend && ./venv/bin/python -m unittest discover -s test -v
"""
import os
import sys
import unittest

import numpy as np

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from fastapi import HTTPException  # noqa: E402

import main  # noqa: E402
from embeddings import EmbeddingSpace  # noqa: E402


def fake_space(words, language):
    m = np.eye(len(words), dtype=np.float32)
    return EmbeddingSpace(words=list(words), word_to_idx={w: i for i, w in enumerate(words)},
                          matrix=m, nn_index=None, language=language,
                          good_mask=np.ones(len(words), dtype=bool))


class TestGuessRules(unittest.TestCase):
    def setUp(self):
        self._saved = dict(main.spaces)
        main.spaces["he"] = fake_space(["קפה", "חלב", "תה", "סוכר"], "he")

    def tearDown(self):
        main.spaces.clear()
        main.spaces.update(self._saved)

    def error_of(self, **kw):
        with self.assertRaises(HTTPException) as cm:
            main.guess(main.GuessRequest(**kw))
        return cm.exception.status_code, cm.exception.detail["error"]

    def test_a_word_said_earlier_in_the_game_is_refused(self):
        self.assertEqual(
            self.error_of(word1="תה", word2="סוכר", player_guess="קפה", round_num=3,
                          used_words=["קפה", "חלב", "תה", "סוכר"]),
            (422, "already_used"))

    def test_a_word_on_screen_keeps_its_own_message(self):
        self.assertEqual(
            self.error_of(word1="תה", word2="סוכר", player_guess="תה", round_num=3,
                          used_words=["קפה", "חלב", "תה", "סוכר"]),
            (422, "same_as_pair"))


if __name__ == "__main__":
    unittest.main()
