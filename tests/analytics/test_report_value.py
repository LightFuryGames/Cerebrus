"""Coverage for the report_value (1-100) universal weight formula."""

from __future__ import annotations

import pytest

from cerebrus.plugins.analytics.core.normalizer import (
    EXPECTED_FIELDS,
    compute_report_value,
)


def _score(**kwargs) -> int:
    defaults = dict(
        frame_count=0,
        duration_s=0,
        target_fps=60,
        missing_count=0,
        total_expected=len(EXPECTED_FIELDS),
    )
    defaults.update(kwargs)
    return compute_report_value(**defaults)


# ---------------------------------------------------------------------------
# Clamping


def test_floor_is_1() -> None:
    assert _score() == max(1, _score())
    assert (
        compute_report_value(
            frame_count=-1,
            duration_s=-1,
            target_fps=60,
            missing_count=len(EXPECTED_FIELDS),
            total_expected=len(EXPECTED_FIELDS),
        )
        == 1
    )


def test_ceiling_is_100() -> None:
    # Saturate all components.
    assert _score(frame_count=36000, duration_s=600, target_fps=60) == 100


# ---------------------------------------------------------------------------
# Monotonicity


def test_longer_capture_scores_higher() -> None:
    short = _score(frame_count=600, duration_s=10, target_fps=60)
    long = _score(frame_count=18000, duration_s=300, target_fps=60)
    assert long > short


def test_more_missing_fields_scores_lower() -> None:
    clean = _score(frame_count=10000, duration_s=200, missing_count=0)
    dirty = _score(frame_count=10000, duration_s=200, missing_count=10)
    assert clean > dirty


def test_off_target_fps_loses_consistency() -> None:
    on_target = _score(frame_count=12000, duration_s=200, target_fps=60)
    off_target = _score(
        frame_count=12000, duration_s=200, target_fps=120
    )  # only 30 fps observed vs 120
    assert on_target >= off_target


# ---------------------------------------------------------------------------
# Component cap behavior


def test_volume_caps_at_36000_frames() -> None:
    cap = _score(frame_count=36000, duration_s=10, target_fps=60)
    over_cap = _score(frame_count=1_000_000, duration_s=10, target_fps=60)
    assert cap == over_cap


def test_duration_caps_at_600_seconds() -> None:
    cap = _score(frame_count=10, duration_s=600, target_fps=60)
    over_cap = _score(frame_count=10, duration_s=99999, target_fps=60)
    assert cap == over_cap


# ---------------------------------------------------------------------------
# Bad inputs


@pytest.mark.parametrize("bad", [None, "", "abc", float("nan")])
def test_garbage_inputs_do_not_crash(bad) -> None:
    score = compute_report_value(
        frame_count=bad,
        duration_s=bad,
        target_fps=bad,
        missing_count=0,
        total_expected=len(EXPECTED_FIELDS),
    )
    assert 1 <= score <= 100


def test_negative_inputs_clamped_to_zero_component() -> None:
    score = compute_report_value(
        frame_count=-1000,
        duration_s=-50,
        target_fps=60,
        missing_count=0,
        total_expected=len(EXPECTED_FIELDS),
    )
    assert score == 15  # 0.15 completeness * 100


def test_zero_target_fps_defaults_to_60() -> None:
    """target_fps=0 must not divide-by-zero in consistency check."""
    score = compute_report_value(
        frame_count=12000,
        duration_s=200,
        target_fps=0,
        missing_count=0,
        total_expected=len(EXPECTED_FIELDS),
    )
    assert 1 <= score <= 100


# ---------------------------------------------------------------------------
# Deterministic + repeatable (no hidden state)


def test_repeatable() -> None:
    args = dict(
        frame_count=14138,
        duration_s=239.76,
        target_fps=60,
        missing_count=0,
        total_expected=len(EXPECTED_FIELDS),
    )
    assert compute_report_value(**args) == compute_report_value(**args)


def test_total_expected_zero_does_not_divide_by_zero() -> None:
    score = compute_report_value(
        frame_count=0,
        duration_s=0,
        target_fps=60,
        missing_count=0,
        total_expected=0,
    )
    assert 1 <= score <= 100
