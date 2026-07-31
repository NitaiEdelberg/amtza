"""Unit tests for game.py — win detection, homing-threshold decay, and messages.

Pure logic: uses small numpy vectors, so it needs no fastText models.
Run:  cd backend && ./venv/bin/python -m unittest discover -s test -v
"""
import os
import sys
import unittest

import numpy as np

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from game import (  # noqa: E402
    WIN_THRESHOLD,
    HOMING_GRACE_ROUNDS,
    HOMING_MIN_THRESHOLD,
    _effective_threshold,
    check_win,
    get_funny_message,
    get_win_message,
    build_round_result,
    EASTER_EGGS,
)


def unit(*vals):
    """A unit-length vector from the given components."""
    v = np.array(vals, dtype=np.float32)
    return v / np.linalg.norm(v)


class TestHomingThreshold(unittest.TestCase):
    def test_full_threshold_during_grace(self):
        self.assertEqual(_effective_threshold(1), WIN_THRESHOLD)
        self.assertEqual(_effective_threshold(HOMING_GRACE_ROUNDS), WIN_THRESHOLD)

    def test_threshold_decays_after_grace(self):
        after = _effective_threshold(HOMING_GRACE_ROUNDS + 1)
        self.assertLess(after, WIN_THRESHOLD)

    def test_threshold_never_below_floor(self):
        # A very high round number should be clamped, not go to zero/negative.
        self.assertEqual(_effective_threshold(1000), HOMING_MIN_THRESHOLD)

    def test_threshold_is_monotonic_non_increasing(self):
        vals = [_effective_threshold(r) for r in range(1, 60)]
        for a, b in zip(vals, vals[1:]):
            self.assertGreaterEqual(a, b)


class TestCheckWin(unittest.TestCase):
    def test_identical_words_win_regardless_of_vectors(self):
        # Same word = win even if the vectors passed are unrelated.
        self.assertTrue(check_win("כוכב", "כוכב", unit(1, 0), unit(0, 1), round_num=1))

    def test_identical_words_case_insensitive(self):
        self.assertTrue(check_win("Star", "star", unit(1, 0), unit(0, 1), round_num=1))

    def test_close_vectors_win(self):
        v = unit(1, 0, 0)
        near = unit(0.98, 0.02, 0)  # cosine well above WIN_THRESHOLD
        self.assertTrue(check_win("a", "b", v, near, round_num=1))

    def test_far_vectors_do_not_win_early(self):
        self.assertFalse(check_win("a", "b", unit(1, 0), unit(0, 1), round_num=1))

    def test_homing_lets_borderline_pair_win_late(self):
        # Two vectors whose similarity sits between the floor and the full bar:
        # a loss during the grace period, a win once the threshold has decayed.
        v1 = unit(1, 0)
        v2 = unit(0.8, 0.6)  # cosine 0.8 — below the 0.85 bar, above the 0.72 floor
        self.assertFalse(check_win("a", "b", v1, v2, round_num=1))
        self.assertTrue(check_win("a", "b", v1, v2, round_num=40))

    def test_related_but_different_words_do_not_win(self):
        # Real fastText cosines for pairs that are clearly NOT the same idea:
        # cat/dog 0.71, king/queen 0.71, brother/father 0.79. At the old 0.70 bar
        # these all "won" and the game claimed both sides said the same thing.
        v1 = unit(1, 0)
        for cos in (0.71, 0.79):
            v2 = unit(cos, (1 - cos ** 2) ** 0.5)
            self.assertFalse(
                check_win("brother", "father", v1, v2, round_num=1),
                f"cosine {cos} should not win during the grace period",
            )


class TestMessages(unittest.TestCase):
    def test_easter_egg_takes_priority(self):
        (w1, w2) = next(iter(EASTER_EGGS))  # a real egg pair from the map
        msg = get_funny_message(0.9, "he", w1, w2)
        self.assertEqual(msg, EASTER_EGGS[frozenset({w1, w2})])

    def test_very_far_and_far_and_medium_tiers(self):
        self.assertIsNotNone(get_funny_message(0.05, "he", "x", "y"))  # very_far
        self.assertIsNotNone(get_funny_message(0.25, "en", "x", "y"))  # far
        self.assertIsNotNone(get_funny_message(0.40, "en", "x", "y"))  # medium

    def test_close_similarity_returns_no_message(self):
        # Above the "medium" band the round isn't mocked as a win, but there's no nag.
        self.assertIsNone(get_funny_message(0.6, "en", "x", "y"))

    def test_win_message_language(self):
        self.assertIn(get_win_message("he"), __import__("game").WIN_MESSAGES_HE)
        self.assertIn(get_win_message("en"), __import__("game").WIN_MESSAGES_EN)

    def test_near_win_message_names_both_words_and_never_claims_sameness(self):
        # A similarity win must not tell the player they "thought the same thing" —
        # it has to show both words. (Regression: brother/father won at the old 0.70
        # bar and reported "You and the computer thought the same thing!")
        msg = get_win_message("en", exact=False, player_word="brother", computer_word="father")
        self.assertIn("brother", msg)
        self.assertIn("father", msg)
        self.assertNotIn("same thing", msg)

    def test_near_win_message_hebrew_formats_both_words(self):
        msg = get_win_message("he", exact=False, player_word="ערב", computer_word="לילה")
        self.assertIn("ערב", msg)
        self.assertIn("לילה", msg)
        self.assertNotIn("{a}", msg)


class TestBuildRoundResult(unittest.TestCase):
    def test_win_result_shape(self):
        v = unit(1, 0)
        r = build_round_result(
            round_num=1, word1="a", word2="b",
            player_guess="star", computer_guess="star",
            player_vec=v, computer_vec=v, midpoint=v, lang="en",
        )
        self.assertTrue(r.is_won)
        self.assertIsNotNone(r.win_message)
        self.assertIsNone(r.funny_message)  # no nag on a win
        self.assertEqual(r.language, "en")

    def test_similarity_win_uses_the_near_win_message(self):
        # Different words that are close enough to win must get the honest
        # "close enough, X vs Y" message, not the exact-match one.
        v1 = unit(1, 0)
        v2 = unit(0.99, 0.141)  # cosine ~0.99: a win, but not the same word
        r = build_round_result(
            round_num=1, word1="a", word2="b",
            player_guess="brother", computer_guess="father",
            player_vec=v1, computer_vec=v2, midpoint=v1, lang="en",
        )
        self.assertTrue(r.is_won)
        self.assertIn("brother", r.win_message)
        self.assertIn("father", r.win_message)

    def test_loss_result_has_funny_not_win(self):
        r = build_round_result(
            round_num=1, word1="fire", word2="ice",
            player_guess="banana", computer_guess="steam",
            player_vec=unit(1, 0), computer_vec=unit(0, 1),
            midpoint=unit(1, 1), lang="en",
        )
        self.assertFalse(r.is_won)
        self.assertIsNone(r.win_message)

    def test_similarities_are_rounded_floats(self):
        r = build_round_result(
            round_num=1, word1="a", word2="b",
            player_guess="p", computer_guess="c",
            player_vec=unit(1, 0), computer_vec=unit(0, 1),
            midpoint=unit(1, 1), lang="en",
        )
        for val in (r.player_similarity, r.computer_similarity, r.player_computer_similarity):
            self.assertIsInstance(val, float)


if __name__ == "__main__":
    unittest.main()
