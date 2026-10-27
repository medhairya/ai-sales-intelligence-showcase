import pytest

from app.llm_client import MockProvider, UpstreamError, build_provider, complete_with_retry


class FlakyProvider:
    name = "flaky"

    def __init__(self, failures: int) -> None:
        self.failures = failures
        self.calls = 0

    def complete(self, prompt: str, timeout: float) -> str:
        self.calls += 1
        if self.calls <= self.failures:
            raise ConnectionError("upstream down")
        return "ok"


def test_retries_then_succeeds_with_backoff():
    sleeps: list[float] = []
    p = FlakyProvider(failures=2)
    out = complete_with_retry(p, "hi", timeout=1, max_retries=2, sleep=sleeps.append)
    assert out == "ok"
    assert p.calls == 3
    assert sleeps == [0.5, 1.0]  # exponential backoff


def test_raises_after_exhausting_retries():
    p = FlakyProvider(failures=10)
    with pytest.raises(UpstreamError):
        complete_with_retry(p, "hi", timeout=1, max_retries=2, sleep=lambda _: None)
    assert p.calls == 3


def test_build_provider():
    assert isinstance(build_provider("mock"), MockProvider)
    with pytest.raises(ValueError):
        build_provider("nope")
