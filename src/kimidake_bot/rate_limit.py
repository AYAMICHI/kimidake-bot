from __future__ import annotations

from collections import defaultdict, deque
from threading import Lock
from time import monotonic


class InMemoryRateLimiter:
    """単一プロセスMVP用の簡易IPレート制限。"""

    def __init__(self, max_requests: int = 3, window_seconds: int = 60):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._requests: dict[str, deque[float]] = defaultdict(deque)
        self._lock = Lock()

    def allow(self, key: str) -> bool:
        now = monotonic()
        cutoff = now - self.window_seconds
        with self._lock:
            timestamps = self._requests[key]
            while timestamps and timestamps[0] <= cutoff:
                timestamps.popleft()
            if len(timestamps) >= self.max_requests:
                return False
            timestamps.append(now)
            return True
