"""Tests for modules.api.retry: RetryPolicy execute, exponential backoff."""

from __future__ import annotations


import pytest

from modules.api.retry import RetryPolicy


def test_retry_policy_success_first_try() -> None:
    policy = RetryPolicy(max_retries=2)
    calls: list[int] = []
    result = policy.execute(lambda: (calls.append(1) or 42))
    assert result == 42
    assert len(calls) == 1
    assert calls[0] == 1


def test_retry_policy_retry_then_success() -> None:
    policy = RetryPolicy(max_retries=2, initial_delay_sec=0.01)
    calls: list[int] = []

    def flaky() -> int:
        calls.append(1)
        if len(calls) < 2:
            raise ValueError("fail")
        return 99

    result = policy.execute(flaky)
    assert result == 99
    assert len(calls) == 2
    assert calls[0] == 1 and calls[1] == 1


def test_retry_policy_exhaust_retries_raises() -> None:
    policy = RetryPolicy(max_retries=2, initial_delay_sec=0.01)
    calls: list[int] = []

    def always_fail() -> int:
        calls.append(1)
        raise ValueError("always fail")

    with pytest.raises(ValueError, match="always fail"):
        policy.execute(always_fail)
    assert len(calls) == 3
    assert isinstance(calls[0], int)


def test_retry_policy_should_retry_false_raises_immediately() -> None:
    policy = RetryPolicy(max_retries=5, initial_delay_sec=0.01)
    calls: list[int] = []

    def fail() -> int:
        calls.append(1)
        raise ValueError("do not retry")

    def should_retry(e: Exception) -> bool:
        return False

    with pytest.raises(ValueError, match="do not retry"):
        policy.execute(fail, should_retry=should_retry)
    assert len(calls) == 1
    assert calls[0] == 1


def test_retry_policy_should_retry_true_retries() -> None:
    policy = RetryPolicy(max_retries=2, initial_delay_sec=0.01)
    calls: list[int] = []

    def fail_twice() -> int:
        calls.append(1)
        if len(calls) < 3:
            raise ValueError("retry me")
        return 1

    def should_retry(e: Exception) -> bool:
        return "retry" in str(e)

    result = policy.execute(fail_twice, should_retry=should_retry)
    assert result == 1
    assert len(calls) == 3


def test_retry_policy_init_clamps_negative_max_retries() -> None:
    policy = RetryPolicy(max_retries=-1)
    assert policy._max_retries == 0
    result = policy.execute(lambda: 1)
    assert result == 1


def test_retry_policy_init_clamps_initial_delay() -> None:
    policy = RetryPolicy(initial_delay_sec=-1.0)
    assert policy._initial_delay == 0.0
    assert policy._max_delay >= 0.0


def test_retry_policy_zero_retries_one_attempt() -> None:
    policy = RetryPolicy(max_retries=0)
    calls: list[int] = []

    def fail() -> int:
        calls.append(1)
        raise ValueError("x")

    with pytest.raises(ValueError, match="x"):
        policy.execute(fail)
    assert len(calls) == 1
