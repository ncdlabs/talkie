"""Tests for profile.constants: numeric constants."""

from __future__ import annotations

from profile.constants import (
    ACCEPTED_DISPLAY_CAP,
    ACCEPTED_PROFILE_LIMIT,
    CORRECTION_DISPLAY_CAP,
    CORRECTION_PROFILE_LIMIT,
    HISTORY_LIST_LIMIT,
)


def test_correction_profile_limit_positive() -> None:
    assert CORRECTION_PROFILE_LIMIT > 0
    assert isinstance(CORRECTION_PROFILE_LIMIT, int)
    assert CORRECTION_PROFILE_LIMIT == 200


def test_accepted_profile_limit_positive() -> None:
    assert ACCEPTED_PROFILE_LIMIT > 0
    assert isinstance(ACCEPTED_PROFILE_LIMIT, int)
    assert ACCEPTED_PROFILE_LIMIT == 50


def test_correction_display_cap_positive() -> None:
    assert CORRECTION_DISPLAY_CAP > 0
    assert isinstance(CORRECTION_DISPLAY_CAP, int)
    assert CORRECTION_DISPLAY_CAP == 50


def test_accepted_display_cap_positive() -> None:
    assert ACCEPTED_DISPLAY_CAP > 0
    assert isinstance(ACCEPTED_DISPLAY_CAP, int)
    assert ACCEPTED_DISPLAY_CAP == 30


def test_history_list_limit_positive() -> None:
    assert HISTORY_LIST_LIMIT > 0
    assert isinstance(HISTORY_LIST_LIMIT, int)
    assert HISTORY_LIST_LIMIT == 100
