"""The anonymous game log must never cost a player anything.

Run:  cd backend && ./venv/bin/python -m unittest discover -s test -v
"""
import json
import os
import sys
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import gamelog  # noqa: E402


class FakeResponse:
    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def read(self):
        return b""


class Recorder:
    def __init__(self, fail=False):
        self.requests, self.fail = [], fail

    def __call__(self, req, timeout=None):
        if self.fail:
            raise OSError("supabase down")
        self.requests.append(req)
        return FakeResponse()


ROW = {"game_id": None, "lang": "en", "round_num": 1, "word1": "apple", "word2": "tree",
       "player_guess": "fruit", "computer_guess": "fruit", "similarity": 1.0, "is_won": True}


class TestGameLog(unittest.TestCase):
    def test_batches_rows_into_one_insert(self):
        rec = Recorder()
        log = gamelog.GameLog("https://x.supabase.co/", "sb_secret_abc", opener=rec)
        for _ in range(3):
            log.record(dict(ROW))
        self.assertEqual(log.flush(), 3)
        self.assertEqual(len(rec.requests), 1)
        req = rec.requests[0]
        self.assertEqual(req.full_url, "https://x.supabase.co/rest/v1/rounds")
        self.assertEqual(len(json.loads(req.data)), 3)

    def test_secret_keys_are_not_sent_as_bearer_tokens(self):
        rec = Recorder()
        log = gamelog.GameLog("https://x.supabase.co", "sb_secret_abc", opener=rec)
        log.record(dict(ROW))
        log.flush()
        headers = {k.lower(): v for k, v in rec.requests[0].header_items()}
        self.assertEqual(headers["apikey"], "sb_secret_abc")
        self.assertNotIn("authorization", headers)

    def test_legacy_jwt_keys_also_go_in_authorization(self):
        rec = Recorder()
        log = gamelog.GameLog("https://x.supabase.co", "eyJhbGciOi.payload.sig", opener=rec)
        log.record(dict(ROW))
        log.flush()
        headers = {k.lower(): v for k, v in rec.requests[0].header_items()}
        self.assertEqual(headers["authorization"], "Bearer eyJhbGciOi.payload.sig")

    def test_a_failing_supabase_drops_rows_instead_of_raising(self):
        log = gamelog.GameLog("https://x.supabase.co", "k", opener=Recorder(fail=True))
        log.record(dict(ROW))
        self.assertEqual(log.flush(), 0)
        self.assertEqual(log.dropped, 1)

    def test_a_full_queue_drops_new_rows_without_blocking(self):
        log = gamelog.GameLog("https://x.supabase.co", "k", opener=Recorder())
        for _ in range(gamelog._QUEUE_MAX + 5):
            log.record(dict(ROW))
        self.assertEqual(log.dropped, 5)

    def test_off_when_not_configured(self):
        saved = {k: os.environ.pop(k, None) for k in ("SUPABASE_URL", "SUPABASE_KEY")}
        try:
            self.assertIsNone(gamelog.start_from_env())
            gamelog.record(dict(ROW))   # a no-op, not an error
        finally:
            for k, v in saved.items():
                if v is not None:
                    os.environ[k] = v


if __name__ == "__main__":
    unittest.main()
