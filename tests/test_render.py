import re
from datetime import datetime
from pathlib import Path

from clock import render as render_mod
from clock.render import render
from clock.state import new_timer
from dataclasses import replace

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
    out = render(state(), (60, 24))
    assert len(out.split("\n")) == 24


def test_too_small_message():
    out = strip(render(state(), (20, 8)))
    assert "WINDOW TOO SMALL" in out


def test_paused_label_shown():
    assert "PAUSED" in strip(render(state(paused=True), (60, 24)))


def test_running_label_remaining_for_minutes():
    assert "REMAINING" in strip(render(state(total=300), (60, 24)))


def test_running_label_seconds_for_sub_minute():
    assert "SECONDS" in strip(render(state(total=30), (60, 24)))


def test_header_shows_date():
    out = strip(render(state(now=T0), (60, 24)))
    assert "May 28" in out
    assert "2:33 PM" in out


def test_hint_present():
    assert "[q] quit" in strip(render(state(), (60, 24)))


def test_render_is_deterministic():
    s, size = state(), (60, 24)
    assert render(s, size) == render(s, size)


def test_static_layer_is_cached():
    render(state(), (60, 24))
    from clock.theme import Layout

    layout = Layout.from_size(60, 24)
    a = render_mod._static_canvas(layout)
    b = render_mod._static_canvas(layout)
    assert a is b


def test_arc_grows_with_remaining():
    # More time remaining => longer gradient arc => more warm-coloured cells.
    def warm_cells(s):
        out = render(s, (60, 24))
        return len(re.findall(r"\x1b\[38;2;(\d+);(\d+);(\d+)m", out))

    # crude proxy: more distinct colour escapes when the arc spans more hues
    full = render(state(total=300, remaining=300), (60, 24))
    near_empty = render(state(total=300, remaining=15), (60, 24))
    assert full.count("\x1b[38;2;") >= near_empty.count("\x1b[38;2;")


def test_matches_golden():
    golden = Path(__file__).parent / "golden_60x24.txt"
    out = strip(render(state(total=300, remaining=215, now=T0), (60, 24)))
    assert out == golden.read_text()
