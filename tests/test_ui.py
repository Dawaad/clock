import re
from dataclasses import replace
from datetime import datetime

from clock.state import new_timer
from clock.ui import render

T0 = datetime(2026, 5, 28, 14, 33, 0)
ANSI = re.compile(r"\x1b\[[0-9;]*m")


def strip(s: str) -> str:
    return ANSI.sub("", s)


def state(total=300, remaining=None, paused=False, now=T0):
    s = new_timer(total, now)
    return replace(
        s,
        remaining=float(total if remaining is None else remaining),
        paused=paused,
    )


def test_output_has_one_line_per_row():
    assert len(render(state(), (110, 40)).split("\n")) == 40


def test_too_small_message():
    assert "WINDOW TOO SMALL" in strip(render(state(), (20, 8)))


def test_all_four_quadrant_headers_present():
    out = strip(render(state(), (110, 40)))
    for header in ("T I M E R", "K E Y B I N D S", "C L O C K", "T I M E"):
        assert header in out


def test_keybinds_listed():
    out = strip(render(state(), (110, 40)))
    assert "pause / resume" in out
    assert "adjust 10s" in out
    assert "quit" in out


def test_wall_time_and_date_shown():
    out = strip(render(state(now=T0), (110, 40)))
    assert "28th of May" in out
    assert "Thursday" in out
    assert "[2026]" in out


def test_status_reflects_pause():
    assert "PAUSED" in strip(render(state(paused=True), (110, 40)))
    assert "RUNNING" in strip(render(state(paused=False), (110, 40)))


def test_clock_percentage_shown():
    out = strip(render(state(total=300, remaining=150), (110, 40)))
    assert "50%" in out


def test_cream_background_emitted():
    assert "48;2;237;234;226" in render(state(), (110, 40))


def test_is_deterministic():
    s, size = state(), (90, 36)
    assert render(s, size) == render(s, size)


def test_renders_on_small_screen_without_error():
    out = render(state(total=190, remaining=90), (80, 20))
    assert len(out.split("\n")) == 20
    assert "ELAPSED" in strip(out)


def test_is_narrow_threshold():
    from clock.ui import NARROW_W, is_narrow

    assert is_narrow(NARROW_W - 1)
    assert not is_narrow(NARROW_W)


def test_stacked_layout_when_narrow():
    from clock.ui import STACK_MIN_H

    out = render(state(), (48, STACK_MIN_H))
    plain = strip(out)
    for header in ("T I M E R", "K E Y B I N D S", "C L O C K", "T I M E"):
        assert header in plain
    assert "ELAPSED" in plain
    assert len(out.split("\n")) == STACK_MIN_H
