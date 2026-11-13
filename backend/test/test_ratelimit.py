"""The per-client limiter: generous for people, a wall for loops.

Run:  cd backend && ./venv/bin/python -m unittest discover -s test -v
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from ratelimit import RateLimiter, client_ip, group_for  # noqa: E402


class FakeClock:
    def __init__(self):
        self.t = 1000.0

    def __call__(self):
        return self.t


class TestRateLimiter(unittest.TestCase):
    def setUp(self):
        self.clock = FakeClock()
        self.rl = RateLimiter({"guess": (3, 1.0)}, clock=self.clock)

    def test_burst_then_refuse(self):
        self.assertEqual([self.rl.allow("guess", "a") for _ in range(4)], [True, True, True, False])

    def test_refills_over_time(self):
        for _ in range(3):
            self.rl.allow("guess", "a")
        self.assertFalse(self.rl.allow("guess", "a"))
        self.clock.t += 1.0
        self.assertTrue(self.rl.allow("guess", "a"))

    def test_clients_are_independent(self):
        for _ in range(3):
            self.rl.allow("guess", "a")
        self.assertFalse(self.rl.allow("guess", "a"))
        self.assertTrue(self.rl.allow("guess", "b"))

    def test_idle_buckets_are_pruned(self):
        for ip in "abcdef":
            self.rl.allow("guess", ip)
        self.clock.t += 120
        self.rl.allow("guess", "z")
        self.assertEqual(len(self.rl), 1)

    def test_a_person_guessing_every_few_seconds_is_never_limited(self):
        rl = RateLimiter(clock=self.clock)
        for _ in range(200):
            self.assertTrue(rl.allow("guess", "a"))
            self.clock.t += 3.0


class TestRouting(unittest.TestCase):
    def test_groups(self):
        self.assertEqual(group_for("POST", "/guess"), "guess")
        self.assertEqual(group_for("POST", "/hint"), "guess")
        self.assertEqual(group_for("GET", "/validate/שלום"), "light")
        self.assertEqual(group_for("GET", "/pair"), "light")
        self.assertIsNone(group_for("GET", "/health"))
        self.assertIsNone(group_for("OPTIONS", "/guess"))   # CORS preflight

    def test_cloudflare_header_wins_over_spoofable_forwarded_for(self):
        h = {"cf-connecting-ip": "1.2.3.4", "x-forwarded-for": "6.6.6.6, 10.0.0.1"}
        self.assertEqual(client_ip(h), "1.2.3.4")
        self.assertEqual(client_ip({"x-forwarded-for": "5.5.5.5, 10.0.0.1"}), "5.5.5.5")
        self.assertEqual(client_ip({}, "9.9.9.9"), "9.9.9.9")


if __name__ == "__main__":
    unittest.main()
