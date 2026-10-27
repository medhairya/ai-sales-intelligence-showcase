"""Provider-agnostic LLM client used by the gateway (the proxy layer).

The gateway talks only to the ``LLMProvider`` interface, so the upstream
provider can be swapped without touching business logic. Transient
upstream failures are retried with exponential backoff.
"""

from __future__ import annotations

import os
import time
from collections.abc import Callable
from typing import Protocol


class UpstreamError(Exception):
    """Raised when the upstream provider fails after all retries."""


class LLMProvider(Protocol):
    name: str

    def complete(self, prompt: str, timeout: float) -> str: ...


class MockProvider:
    """Deterministic provider for local runs, tests and CI (no API key needed)."""

    name = "mock"

    def complete(self, prompt: str, timeout: float) -> str:
        return f"[mock reply] Summary of request: {prompt[:120]}"


class OpenAIProvider:
    """Calls an OpenAI-compatible chat completions endpoint over HTTP."""

    name = "openai"

    def __init__(self, api_key: str | None = None, model: str = "gpt-4o-mini") -> None:
        self.api_key = api_key or os.environ["OPENAI_API_KEY"]
        self.model = model
        self.base_url = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")

    def complete(self, prompt: str, timeout: float) -> str:
        import httpx

        resp = httpx.post(
            f"{self.base_url}/chat/completions",
            headers={"Authorization": f"Bearer {self.api_key}"},
            json={"model": self.model, "messages": [{"role": "user", "content": prompt}]},
            timeout=timeout,
        )
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"]


def build_provider(name: str) -> LLMProvider:
    if name == "mock":
        return MockProvider()
    if name == "openai":
        return OpenAIProvider()
    raise ValueError(f"unknown LLM provider: {name}")


def complete_with_retry(
    provider: LLMProvider,
    prompt: str,
    timeout: float,
    max_retries: int,
    sleep: Callable[[float], None] = time.sleep,
    base_delay: float = 0.5,
) -> str:
    last_exc: Exception | None = None
    for attempt in range(max_retries + 1):
        try:
            return provider.complete(prompt, timeout)
        except Exception as exc:  # noqa: BLE001 - any upstream failure is retryable here
            last_exc = exc
            if attempt < max_retries:
                sleep(base_delay * (2**attempt))
    raise UpstreamError(str(last_exc)) from last_exc
