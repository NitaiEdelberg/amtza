"""Anonymous record of real games, for improving the computer's middle word.

WHY. Every quality number in this repo comes from a model standing in for a
player (scripts/eval_human.py, the play-test agents). Real games are the ground
truth they approximate: which pairs people actually see, what they answer, and
where they give up. Collecting them is the only way to check those proxies.

WHAT IS STORED, per round: a random game id the browser makes up for each game
(not tied to a person or device), the language, the round number, the two words
on screen, both guesses, their similarity and whether it was a win. Nothing
else: no IP address, no user agent, no account, no timestamp finer than the row's
own created_at. supabase/schema.sql has the table.

HOW. Off unless SUPABASE_URL and SUPABASE_KEY are set. When on, /guess only puts
a row on a bounded in-memory queue; a daemon thread sends batches to Supabase's
REST API every few seconds. A slow or failing Supabase therefore never slows a
guess: rows that can't be sent are logged and dropped, and when the queue is full
new rows are dropped rather than waiting. Losing a few rows of telemetry is fine;
making a player wait for it is not.

SUPABASE_KEY is the project's secret (service-role) key. It lives only in the
backend's environment; the table has row-level security on and no policies, so
the public anon key can neither read nor write it.
"""
import json
import logging
import os
import queue
import threading
import time
import urllib.request

logger = logging.getLogger(__name__)

TABLE = "rounds"
_BATCH_MAX = 100
_FLUSH_EVERY = 5.0       # seconds
_QUEUE_MAX = 2000
_TIMEOUT = 10            # seconds per HTTP call


class GameLog:
    def __init__(self, url: str, key: str, opener=urllib.request.urlopen):
        self.endpoint = f"{url.rstrip('/')}/rest/v1/{TABLE}"
        self.key = key
        self.opener = opener
        self.q = queue.Queue(maxsize=_QUEUE_MAX)
        self.dropped = 0
        self.sent = 0

    def record(self, row: dict) -> None:
        """Queue a row. Never blocks; drops the row if the queue is full."""
        try:
            self.q.put_nowait(row)
        except queue.Full:
            self.dropped += 1

    def _headers(self) -> dict:
        h = {"apikey": self.key, "Content-Type": "application/json",
             "Prefer": "return=minimal"}
        # Legacy service-role keys are JWTs and also go in Authorization. The newer
        # sb_secret_ keys are not JWTs and must not.
        if self.key.startswith("eyJ"):
            h["Authorization"] = f"Bearer {self.key}"
        return h

    def flush(self) -> int:
        """Send what is queued, in batches. Returns rows sent."""
        sent = 0
        while True:
            batch = []
            while len(batch) < _BATCH_MAX:
                try:
                    batch.append(self.q.get_nowait())
                except queue.Empty:
                    break
            if not batch:
                return sent
            req = urllib.request.Request(self.endpoint, data=json.dumps(batch).encode("utf-8"),
                                         headers=self._headers(), method="POST")
            try:
                with self.opener(req, timeout=_TIMEOUT) as resp:
                    resp.read()
                sent += len(batch)
                self.sent += len(batch)
            except Exception as e:  # network, 4xx/5xx: telemetry is never worth a retry storm
                self.dropped += len(batch)
                logger.warning(f"gamelog: dropped {len(batch)} rows ({type(e).__name__}: {e})")

    def run_forever(self):
        while True:
            time.sleep(_FLUSH_EVERY)
            self.flush()


_log = None


def start_from_env() -> "GameLog | None":
    """Start the background sender if configured; return it (or None)."""
    global _log
    url, key = os.getenv("SUPABASE_URL", ""), os.getenv("SUPABASE_KEY", "")
    if not url or not key:
        logger.info("gamelog: off (SUPABASE_URL / SUPABASE_KEY not set)")
        return None
    _log = GameLog(url, key)
    threading.Thread(target=_log.run_forever, name="gamelog", daemon=True).start()
    logger.info(f"gamelog: on, writing to {_log.endpoint}")
    return _log


def record(row: dict) -> None:
    if _log is not None:
        _log.record(row)
