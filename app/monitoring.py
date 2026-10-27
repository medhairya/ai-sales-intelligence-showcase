"""Lightweight in-process metrics for LLM traffic.

Tracks request counts, outcomes, guardrail hits and latency percentiles,
exposed at ``GET /metrics``. In production these would be exported to a
metrics backend (e.g. Prometheus / CloudWatch) and alerted on.
"""

from __future__ import annotations

import threading
from collections import Counter, deque


class Metrics:
    def __init__(self, window: int = 1000) -> None:
        self._lock = threading.Lock()
        self.counters: Counter[str] = Counter()
        self._latencies_ms: deque[float] = deque(maxlen=window)

    def incr(self, name: str, amount: int = 1) -> None:
        with self._lock:
            self.counters[name] += amount

    def observe_latency(self, ms: float) -> None:
        with self._lock:
            self._latencies_ms.append(ms)

    @staticmethod
    def _percentile(sorted_vals: list[float], pct: float) -> float:
        if not sorted_vals:
            return 0.0
        idx = min(len(sorted_vals) - 1, round(pct / 100 * (len(sorted_vals) - 1)))
        return round(sorted_vals[idx], 2)

    def snapshot(self) -> dict:
        with self._lock:
            lat = sorted(self._latencies_ms)
            total = self.counters["requests_total"]
            ok = self.counters["requests_ok"]
            return {
                "counters": dict(self.counters),
                "success_rate": round(ok / total, 4) if total else None,
                "latency_ms": {
                    "p50": self._percentile(lat, 50),
                    "p95": self._percentile(lat, 95),
                    "p99": self._percentile(lat, 99),
                },
            }
