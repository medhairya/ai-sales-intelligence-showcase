"""Per-client token-bucket rate limiter.

Each client gets a bucket holding up to ``capacity`` tokens. A request
consumes one token; tokens refill continuously at ``refill_rate`` per
second. This allows short bursts while capping sustained throughput,
which protects the upstream LLM provider (and its bill) from spikes.

The in-memory backend is thread-safe and suits a single instance. For
several instances behind a load balancer, implement ``RateLimiter``
against a shared store such as Redis.
"""

from __future__ import annotations

import threading
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Protocol


@dataclass
class Decision:
    allowed: bool
    remaining: int
    retry_after: float  # seconds until one token is available (0 if allowed)


class RateLimiter(Protocol):
    def check(self, key: str) -> Decision: ...


@dataclass
class _Bucket:
    tokens: float
    updated_at: float


class TokenBucketLimiter:
    def __init__(
        self,
        capacity: int,
        refill_rate: float,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        if capacity <= 0 or refill_rate <= 0:
            raise ValueError("capacity and refill_rate must be positive")
        self.capacity = capacity
        self.refill_rate = refill_rate
        self._clock = clock
        self._buckets: dict[str, _Bucket] = {}
        self._lock = threading.Lock()

    def check(self, key: str) -> Decision:
        now = self._clock()
        with self._lock:
            bucket = self._buckets.get(key)
            if bucket is None:
                bucket = _Bucket(tokens=float(self.capacity), updated_at=now)
                self._buckets[key] = bucket

            elapsed = max(0.0, now - bucket.updated_at)
            bucket.tokens = min(self.capacity, bucket.tokens + elapsed * self.refill_rate)
            bucket.updated_at = now

            if bucket.tokens >= 1.0:
                bucket.tokens -= 1.0
                return Decision(True, int(bucket.tokens), 0.0)

            retry_after = (1.0 - bucket.tokens) / self.refill_rate
            return Decision(False, 0, retry_after)
