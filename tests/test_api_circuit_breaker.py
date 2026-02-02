"""Tests for modules.api.circuit_breaker: CircuitState, CircuitBreaker call, state transitions."""

from __future__ import annotations

import time

import pytest

from modules.api.circuit_breaker import CircuitBreaker, CircuitState


def test_circuit_breaker_closed_success() -> None:
    cb = CircuitBreaker(failure_threshold=2, recovery_timeout_sec=60.0)
    result = cb.call(lambda: 42)
    assert result == 42
    assert cb._state == CircuitState.CLOSED
    assert cb._failure_count == 0


def _raise_value_error(msg: str = "err") -> None:
    raise ValueError(msg)


def test_circuit_breaker_closed_failure_increments_count() -> None:
    cb = CircuitBreaker(failure_threshold=3, recovery_timeout_sec=60.0)
    with pytest.raises(ValueError, match="err"):
        cb.call(lambda: _raise_value_error("err"))
    assert cb._state == CircuitState.CLOSED
    assert cb._failure_count == 1


def test_circuit_breaker_opens_after_threshold() -> None:
    cb = CircuitBreaker(failure_threshold=2, recovery_timeout_sec=60.0)
    for _ in range(2):
        with pytest.raises(ValueError):
            cb.call(lambda: _raise_value_error("fail"))
    assert cb._state == CircuitState.OPEN
    assert cb._failure_count >= 2
    with pytest.raises(RuntimeError, match="Circuit breaker is OPEN"):
        cb.call(lambda: 1)


def test_circuit_breaker_half_open_after_recovery_timeout() -> None:
    cb = CircuitBreaker(failure_threshold=1, recovery_timeout_sec=1.0)
    with pytest.raises(ValueError):
        cb.call(lambda: _raise_value_error("fail"))
    assert cb._state == CircuitState.OPEN
    time.sleep(1.2)
    result = cb.call(lambda: 100)
    assert result == 100
    assert cb._state == CircuitState.CLOSED


def test_circuit_breaker_half_open_failure_reopens() -> None:
    cb = CircuitBreaker(failure_threshold=1, recovery_timeout_sec=1.0)
    with pytest.raises(ValueError):
        cb.call(lambda: _raise_value_error("fail"))
    assert cb._state == CircuitState.OPEN
    time.sleep(1.2)
    with pytest.raises(ValueError):
        cb.call(lambda: _raise_value_error("again"))
    assert cb._state == CircuitState.OPEN
    assert cb._state == CircuitState.OPEN


def test_circuit_breaker_init_clamps_threshold() -> None:
    cb = CircuitBreaker(failure_threshold=0, recovery_timeout_sec=10.0)
    assert cb._failure_threshold >= 1
    cb2 = CircuitBreaker(failure_threshold=-1)
    assert cb2._failure_threshold >= 1


def test_circuit_breaker_init_clamps_recovery_timeout() -> None:
    cb = CircuitBreaker(failure_threshold=1, recovery_timeout_sec=0)
    assert cb._recovery_timeout_sec >= 1.0


def test_circuit_state_enum_values() -> None:
    assert CircuitState.CLOSED.value == "closed"
    assert CircuitState.OPEN.value == "open"
    assert CircuitState.HALF_OPEN.value == "half_open"
