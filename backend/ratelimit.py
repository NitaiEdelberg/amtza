"""Per-client request limits, so one script can't use up a shared free server.

WHY. The free Render instance has 0.1 of a CPU. Measured on the live service it
tops out around 12 guesses a second, and everyone shares that. A single client
looping on /guess would hand every real player a multi-second wait.

HOW. A token bucket per client IP and route group, in memory. Nothing is
persisted: the service runs as one process, and losing the counters on a restart
only resets everyone to a full bucket. Stale buckets are pruned as we go, so the
dict cannot grow without bound.

THE LIMITS ARE GENEROUS ON PURPOSE. A person guesses every few seconds at most,
but people in one office or on one mobile carrier often share a single public
IP, and a LinkedIn post sends exactly that kind of crowd. The numbers below let
several people behind one address play normally while still stopping a loop.

WHICH IP. The service sits behind Render's proxy, which sits behind Cloudflare
(responses carry cf-ray). CF-Connecting-IP is set by Cloudflare and overwrites
anything a client sends; X-Forwarded-For's first entry can be written by the
client, so it is only a fallback.
"""
import threading
import time

# group -> (bucket size, refill per second)
LIMITS = {
    "guess": (20, 1.0),      # /guess and /hint: burst of 20, then 60/min
    "light": (60, 4.0),      # /validate and /pair: cheap, called while typing
}

_PRUNE_EVERY = 60.0          # seconds between sweeps of idle buckets


class RateLimiter:
    def __init__(self, limits=LIMITS, clock=time.monotonic):
        self.limits = limits
        self.clock = clock
        self._buckets = {}   # (group, ip) -> [tokens, last_update]
        self._lock = threading.Lock()
        self._last_prune = clock()

    def allow(self, group: str, ip: str) -> bool:
        size, rate = self.limits[group]
        now = self.clock()
        with self._lock:
            if now - self._last_prune > _PRUNE_EVERY:
                self._prune(now)
            tokens, last = self._buckets.get((group, ip), (float(size), now))
            tokens = min(size, tokens + (now - last) * rate)
            if tokens < 1.0:
                self._buckets[(group, ip)] = [tokens, now]
                return False
            self._buckets[(group, ip)] = [tokens - 1.0, now]
            return True

    def _prune(self, now):
        # A bucket idle long enough to have refilled completely is the same as
        # no bucket at all.
        for key, (tokens, last) in list(self._buckets.items()):
            size, rate = self.limits[key[0]]
            if tokens + (now - last) * rate >= size:
                del self._buckets[key]
        self._last_prune = now

    def __len__(self):
        return len(self._buckets)


def client_ip(headers, fallback: str = "") -> str:
    cf = headers.get("cf-connecting-ip")
    if cf:
        return cf.strip()
    xff = headers.get("x-forwarded-for")
    if xff:
        return xff.split(",")[0].strip()
    return fallback or "unknown"


def group_for(method: str, path: str) -> "str | None":
    if method == "POST" and path in ("/guess", "/hint"):
        return "guess"
    if method == "GET" and (path == "/pair" or path.startswith("/validate/")):
        return "light"
    return None   # /health and anything else: never limited
