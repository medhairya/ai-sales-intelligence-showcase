import pytest

from app.rate_limiter import TokenBucketLimiter


class FakeClock:
    def __init__(self) -> None:
        self.t = 0.0

    def __call__(self) -> float:
        return self.t


def test_allows_burst_up_to_capacity_then_blocks():
    clock = FakeClock()
    rl = TokenBucketLimiter(capacity=3, refill_rate=1.0, clock=clock)
    assert [rl.check("a").allowed for _ in range(3)] == [True, True, True]
    blocked = rl.check("a")
    assert not blocked.allowed
    assert blocked.retry_after == pytest.approx(1.0)


def test_refills_over_time():
    clock = FakeClock()
    rl = TokenBucketLimiter(capacity=2, refill_rate=2.0, clock=clock)
    rl.check("a")
    rl.check("a")
    assert not rl.check("a").allowed
    clock.t += 0.5  # 0.5s * 2 tokens/s = 1 token
    assert rl.check("a").allowed


def test_never_exceeds_capacity_after_long_idle():
    clock = FakeClock()
    rl = TokenBucketLimiter(capacity=2, refill_rate=10.0, clock=clock)
    clock.t += 1000
    results = [rl.check("a").allowed for _ in range(3)]
    assert results == [True, True, False]


def test_clients_are_isolated():
    clock = FakeClock()
    rl = TokenBucketLimiter(capacity=1, refill_rate=1.0, clock=clock)
    assert rl.check("a").allowed
    assert not rl.check("a").allowed
    assert rl.check("b").allowed


@pytest.mark.parametrize("capacity,rate", [(0, 1.0), (1, 0.0), (-1, 1.0)])
def test_rejects_invalid_config(capacity, rate):
    with pytest.raises(ValueError):
        TokenBucketLimiter(capacity=capacity, refill_rate=rate)
