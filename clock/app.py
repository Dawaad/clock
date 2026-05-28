"""Textual application: drives the clocks, input, and frame refresh.

Timer logic lives in :mod:`clock.state` and all drawing in :mod:`clock.ui`; this
layer only wires real clocks and key events to those pure pieces, so it stays
thin and the logic stays unit-testable.
"""

from __future__ import annotations

import time
from datetime import datetime
from typing import Callable

from rich.text import Text
from textual.app import App, ComposeResult
from textual.containers import VerticalScroll
from textual.css.query import NoMatches
from textual.widgets import Static

from .state import advance, apply_key, new_timer, with_now
from .ui import STACK_MIN_H, is_narrow, render

_SCROLL_KEYS = {"up", "down", "pageup", "pagedown", "home", "end"}

# Textual key names -> timer reducer key tokens.
_KEY_MAP = {
    "space": " ",
    "p": "p",
    "plus": "+",
    "equals_sign": "=",
    "minus": "-",
    "underscore": "_",
}

DEFAULT_FPS = 10
FINISH_BELLS = 4
FINISH_LINGER = 2.0


class ClockApp(App):
    CSS = """
    Screen { background: rgb(237,234,226); }
    #scroll { width: 100%; height: 100%; overflow-x: hidden; overflow-y: auto; }
    #frame { width: auto; height: auto; }
    """

    def __init__(
        self,
        total_seconds: int,
        *,
        monotonic: Callable[[], float] = time.monotonic,
        wallclock: Callable[[], datetime] = datetime.now,
        fps: int = DEFAULT_FPS,
    ) -> None:
        super().__init__()
        self._monotonic = monotonic
        self._wallclock = wallclock
        self._fps = fps
        self._last = 0.0
        self._alerted = False
        self.state = new_timer(total_seconds, wallclock())

    def compose(self) -> ComposeResult:
        with VerticalScroll(id="scroll"):
            yield Static(id="frame")

    def on_mount(self) -> None:
        self._last = self._monotonic()
        self.set_interval(1 / self._fps, self._tick)
        self._draw()

    def _tick(self) -> None:
        now = self._monotonic()
        dt, self._last = now - self._last, now
        self.state = with_now(advance(self.state, dt), self._wallclock())
        if self.state.finished and not self._alerted:
            self._on_finished()
        self._draw()

    def _on_finished(self) -> None:
        self._alerted = True
        for _ in range(FINISH_BELLS):
            self.bell()
        self.set_timer(FINISH_LINGER, self.exit)

    def on_key(self, event) -> None:
        key = event.key
        if key == "q":
            self.exit()
            return
        if key in _SCROLL_KEYS:
            self._scroll(key)
            return
        token = _KEY_MAP.get(key)
        if token is not None:
            self.state = apply_key(self.state, token)
            self._draw()

    def on_resize(self, event) -> None:
        self._draw()

    def _scroll(self, key: str) -> None:
        try:
            sc = self.query_one("#scroll", VerticalScroll)
        except NoMatches:
            return
        if key == "up":
            sc.scroll_up()
        elif key == "down":
            sc.scroll_down()
        elif key == "pageup":
            sc.scroll_page_up()
        elif key == "pagedown":
            sc.scroll_page_down()
        elif key == "home":
            sc.scroll_home()
        elif key == "end":
            sc.scroll_end()

    def _draw(self) -> None:
        # A scheduled interval tick can fire during teardown, after the widget
        # has been unmounted; skip drawing rather than crash.
        if not self.is_running:
            return
        try:
            frame_widget = self.query_one("#frame", Static)
        except NoMatches:
            return
        w, vh = self.size.width, self.size.height
        if is_narrow(w) and STACK_MIN_H > vh:
            # Stacked content is taller than the viewport: render its full height
            # (less one column for the scrollbar) so the container can scroll it.
            frame = render(self.state, (w - 1, STACK_MIN_H))
        else:
            frame = render(self.state, (w, vh))
        frame_widget.update(Text.from_ansi(frame))


def run(total_seconds: int) -> None:
    ClockApp(total_seconds).run()
