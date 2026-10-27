"""Runtime configuration loaded from environment variables."""

from __future__ import annotations

import os
from dataclasses import dataclass


def _int(name: str, default: int) -> int:
    return int(os.getenv(name, str(default)))


def _float(name: str, default: float) -> float:
    return float(os.getenv(name, str(default)))


@dataclass(frozen=True)
class Settings:
    rate_limit_capacity: int = 20          # max burst of requests per client
    rate_limit_refill_per_sec: float = 1.0  # sustained requests/sec per client
    max_prompt_chars: int = 4000
    upstream_timeout_sec: float = 30.0
    upstream_max_retries: int = 2
    llm_provider: str = "mock"              # "mock" or "openai"

    @classmethod
    def from_env(cls) -> Settings:
        return cls(
            rate_limit_capacity=_int("RATE_LIMIT_CAPACITY", cls.rate_limit_capacity),
            rate_limit_refill_per_sec=_float(
                "RATE_LIMIT_REFILL_PER_SEC", cls.rate_limit_refill_per_sec
            ),
            max_prompt_chars=_int("MAX_PROMPT_CHARS", cls.max_prompt_chars),
            upstream_timeout_sec=_float("UPSTREAM_TIMEOUT_SEC", cls.upstream_timeout_sec),
            upstream_max_retries=_int("UPSTREAM_MAX_RETRIES", cls.upstream_max_retries),
            llm_provider=os.getenv("LLM_PROVIDER", cls.llm_provider),
        )
