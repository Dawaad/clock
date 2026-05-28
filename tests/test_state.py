from datetime import datetime, timedelta

import pytest

from clock.state import advance, apply_key, new_timer, with_now

T0 = datetime(2026, 5, 28, 14, 33, 0)


def make(total=60, remaining=None, paused=False):
    s = new_timer(total, T0)
    from dataclasses import replace

    return replace(
        s,
        remaining=float(total if remaining is None else remaining),
        paused=paused,
    )


def test_new_timer_defaults():
    s = new_timer(120, T0)
    assert s.remaining == 120.0
    assert s.total_seconds == 120
    assert s.paused is False
    assert s.fraction == 1.0
    assert s.elapsed == 0.0
    assert s.finished is False


def test_advance_counts_down():
    s = advance(make(60), 5)
    assert s.remaining == 55
    assert s.elapsed == 5


def test_advance_clamps_at_zero():
    s = advance(make(60, remaining=3), 10)
    assert s.remaining == 0
    assert s.finished is True


def test_advance_noop_when_paused():
    s = make(60, paused=True)
    assert advance(s, 5) is s


def test_advance_noop_when_finished():
    s = make(60, remaining=0)
    assert advance(s, 5) is s


def test_advance_ignores_nonpositive_dt():
    s = make(60)
    assert advance(s, 0) is s
    assert advance(s, -1) is s


def test_fraction_clamped():
    assert make(60, remaining=120).fraction == 1.0
    assert make(60, remaining=30).fraction == 0.5
    assert make(60, remaining=0).fraction == 0.0


@pytest.mark.parametrize("key", [" ", "p"])
def test_pause_toggles(key):
    s = make(60)
    paused = apply_key(s, key)
    assert paused.paused is True
    assert apply_key(paused, key).paused is False


@pytest.mark.parametrize("key", ["+", "="])
def test_add_extends_remaining(key):
    s = apply_key(make(60, remaining=20), key, step=10)
    assert s.remaining == 30
    assert s.total_seconds == 60  # denominator unchanged when room exists


def test_add_grows_total_when_exceeding():
    s = apply_key(make(60, remaining=55), "+", step=10)
    assert s.remaining == 65
    assert s.total_seconds == 65
    assert s.fraction == 1.0


@pytest.mark.parametrize("key", ["-", "_"])
def test_subtract_reduces_remaining(key):
    s = apply_key(make(60, remaining=20), key, step=10)
    assert s.remaining == 10


def test_subtract_clamps_at_zero():
    s = apply_key(make(60, remaining=5), "-", step=10)
    assert s.remaining == 0


def test_add_resurrects_finished_timer():
    s = apply_key(make(60, remaining=0), "+", step=10)
    assert s.finished is False
    assert s.remaining == 10


def test_unknown_key_is_noop():
    s = make(60)
    assert apply_key(s, "x") is s


def test_with_now_updates_only_clock():
    s = make(60)
    later = T0 + timedelta(seconds=42)
    updated = with_now(s, later)
    assert updated.now == later
    assert updated.remaining == s.remaining
