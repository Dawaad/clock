from datetime import datetime, timedelta

import pytest

from clock.keys import FOCUS_ORDER, Section
from clock.state import (
    Stopwatch,
    View,
    adjust,
    advance,
    focus_next,
    focus_prev,
    new_timer,
    sw_reset,
    toggle_pause,
    with_now,
)

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


def test_toggle_pause():
    s = make(60)
    paused = toggle_pause(s)
    assert paused.paused is True
    assert toggle_pause(paused).paused is False


def test_adjust_up_extends_remaining():
    s = adjust(make(60, remaining=20), 10)
    assert s.remaining == 30
    assert s.total_seconds == 60  # denominator unchanged when room exists


def test_adjust_up_grows_total_when_exceeding():
    s = adjust(make(60, remaining=55), 10)
    assert s.remaining == 65
    assert s.total_seconds == 65
    assert s.fraction == 1.0


def test_adjust_down_reduces_remaining():
    s = adjust(make(60, remaining=20), -10)
    assert s.remaining == 10
    assert s.total_seconds == 60  # denominator untouched when shrinking


def test_adjust_down_clamps_at_zero():
    s = adjust(make(60, remaining=5), -10)
    assert s.remaining == 0


def test_adjust_up_resurrects_finished_timer():
    s = adjust(make(60, remaining=0), 10)
    assert s.finished is False
    assert s.remaining == 10


def test_sw_reset_zeros_and_stops():
    assert sw_reset(Stopwatch(elapsed=42.0, running=True)) == Stopwatch()


def test_focus_next_cycles_in_order():
    v = View()  # TIMER by default
    assert v.active is FOCUS_ORDER[0]
    seen = [v.active]
    for _ in range(len(FOCUS_ORDER) - 1):
        v = focus_next(v)
        seen.append(v.active)
    assert seen == list(FOCUS_ORDER)


def test_focus_next_wraps_around():
    v = View(active=FOCUS_ORDER[-1])
    assert focus_next(v).active is FOCUS_ORDER[0]


def test_focus_prev_wraps_around():
    v = View(active=FOCUS_ORDER[0])
    assert focus_prev(v).active is FOCUS_ORDER[-1]


def test_focus_next_prev_round_trip():
    v = View(active=Section.STOPWATCH)
    assert focus_prev(focus_next(v)) == v


def test_with_now_updates_only_clock():
    s = make(60)
    later = T0 + timedelta(seconds=42)
    updated = with_now(s, later)
    assert updated.now == later
    assert updated.remaining == s.remaining
