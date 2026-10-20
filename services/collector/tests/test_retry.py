import pytest

from netpulse_collector.repository import PortStatsWriteError, TransientPortStatsWriteError
from netpulse_collector.retry import RetryingPortStatsRepository, RetryPolicy
from netpulse_core import PortStatsReport

REPORT = PortStatsReport(switches=())


class FlakyRepository:
    def __init__(self, failures: list[PortStatsWriteError]) -> None:
        self._failures = failures
        self.calls = 0

    async def save(self, report: PortStatsReport) -> None:
        self.calls += 1
        if self._failures:
            raise self._failures.pop(0)


class RecordingSleep:
    def __init__(self) -> None:
        self.delays: list[float] = []

    async def __call__(self, seconds: float) -> None:
        self.delays.append(seconds)


POLICY = RetryPolicy(attempts=4, base_delay_seconds=0.5)


async def test_transient_failures_are_retried_with_exponential_backoff() -> None:
    inner = FlakyRepository(
        [TransientPortStatsWriteError("down"), TransientPortStatsWriteError("down")]
    )
    sleep = RecordingSleep()

    await RetryingPortStatsRepository(inner, POLICY, sleep=sleep).save(REPORT)

    assert inner.calls == 3
    assert sleep.delays == [0.5, 1.0]


async def test_retries_are_bounded_and_the_last_error_propagates() -> None:
    inner = FlakyRepository([TransientPortStatsWriteError(str(n)) for n in range(5)])
    sleep = RecordingSleep()

    with pytest.raises(TransientPortStatsWriteError, match="3"):
        await RetryingPortStatsRepository(inner, POLICY, sleep=sleep).save(REPORT)

    assert inner.calls == 4
    assert sleep.delays == [0.5, 1.0, 2.0]


async def test_permanent_failures_are_not_retried() -> None:
    inner = FlakyRepository([PortStatsWriteError("bad data")])
    sleep = RecordingSleep()

    with pytest.raises(PortStatsWriteError, match="bad data"):
        await RetryingPortStatsRepository(inner, POLICY, sleep=sleep).save(REPORT)

    assert inner.calls == 1
    assert sleep.delays == []


def test_retry_policy_requires_at_least_one_attempt() -> None:
    with pytest.raises(ValueError, match="attempts"):
        RetryPolicy(attempts=0, base_delay_seconds=0.5)
