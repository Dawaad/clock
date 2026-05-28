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
from textual.color import Color
from textual.containers import VerticalScroll
from textual.css.query import NoMatches
from textual.widgets import Static

from .config import Config
from .keys import Action, dispatch
from .parse import DurationError, parse_duration
from .state import (
    DEFAULT_STEP,
    Editor,
    Stopwatch,
    View,
    adjust,
    advance,
    focus_next,
    focus_prev,
    new_timer,
    sw_reset,
    sw_tick,
    sw_toggle,
    toggle_pause,
    with_now,
)
from .ui import STACK_MIN_H, active_band, content_min_height, render

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
        total_seconds: int | None,
        *,
        config: Config | None = None,
        monotonic: Callable[[], float] = time.monotonic,
        wallclock: Callable[[], datetime] = datetime.now,
        fps: int = DEFAULT_FPS,
    ) -> None:
        super().__init__()
        self._cfg = config or Config()
        self._monotonic = monotonic
        self._wallclock = wallclock
        self._fps = fps
        self._last = 0.0
        self._alerted = False
        self._configured = total_seconds is not None
        self.state = new_timer(total_seconds or 0, wallclock())
        self.stopwatch = Stopwatch()
        self.view = View()
        self.editor = Editor()
        self._keybinds = dict(self._cfg.keybinds)
        self._last_frame: str | None = None
        self._rendered_h = STACK_MIN_H

    def compose(self) -> ComposeResult:
        with VerticalScroll(id="scroll"):
            yield Static(id="frame")

    def on_mount(self) -> None:
        self.screen.styles.background = Color(*self._cfg.colors.bg)
        self._last = self._monotonic()
        self.set_interval(1 / self._fps, self._tick)
        self._draw()

    def _tick(self) -> None:
        now = self._monotonic()
        dt, self._last = now - self._last, now
        # The stopwatch runs independently of whether a countdown is configured.
        self.stopwatch = sw_tick(self.stopwatch, dt)
        if self._configured:
            self.state = advance(self.state, dt)
            if self.state.finished and not self._alerted:
                self._on_finished()
        self.state = with_now(self.state, self._wallclock())
        self._draw()

    def _on_finished(self) -> None:
        self._alerted = True
        for _ in range(FINISH_BELLS):
            self.bell()
        self.set_timer(FINISH_LINGER, self.exit)

    def on_key(self, event) -> None:
        # While the inline duration editor is open it owns all keystrokes so
        # typing a duration never triggers section actions.
        if self.editor.active:
            self._edit_key(event)
            return
        action = dispatch(self.view.active, event.key, self._keybinds)
        if action is not None:
            self._apply(action)

    def _edit_key(self, event) -> None:
        key = event.key
        if key == "enter":
            self._commit_edit()
        elif key == "escape":
            self.editor = Editor()
            self._draw()
        elif key == "backspace":
            self.editor = Editor(active=True, buffer=self.editor.buffer[:-1])
            self._draw()
        elif event.character and event.character.isprintable() and len(event.character) == 1:
            self.editor = Editor(active=True, buffer=self.editor.buffer + event.character)
            self._draw()

    def _commit_edit(self) -> None:
        try:
            total = parse_duration(self.editor.buffer)
        except DurationError as exc:
            self.editor = Editor(active=True, buffer=self.editor.buffer, error=str(exc))
            self._draw()
            return
        self.editor = Editor()
        self.state = new_timer(total, self._wallclock())
        self._configured = True
        self._alerted = False
        self._last = self._monotonic()
        self._draw()

    def _apply(self, action: Action) -> None:
        if action is Action.QUIT:
            self.exit()
            return
        if action is Action.SET_TIMER:
            self.editor = Editor(active=True)
            self._draw()
            return
        if action is Action.FOCUS_NEXT:
            self.view = focus_next(self.view)
            self.call_after_refresh(self._scroll_to_focus)
        elif action is Action.FOCUS_PREV:
            self.view = focus_prev(self.view)
            self.call_after_refresh(self._scroll_to_focus)
        elif action is Action.PAUSE:
            self.state = toggle_pause(self.state)
        elif action is Action.ADJUST_UP:
            self.state = adjust(self.state, DEFAULT_STEP)
        elif action is Action.ADJUST_DOWN:
            self.state = adjust(self.state, -DEFAULT_STEP)
        elif action is Action.SW_TOGGLE:
            self.stopwatch = sw_toggle(self.stopwatch)
        elif action is Action.SW_RESET:
            self.stopwatch = sw_reset(self.stopwatch)
        elif action is Action.CLEAR_TIMER:
            self.state = new_timer(0, self._wallclock())
            self._configured = False
            self._alerted = False
        self._draw()

    def _scroll_to_focus(self) -> None:
        """Bring the focused section's band into view (no-op when it all fits)."""
        try:
            sc = self.query_one("#scroll", VerticalScroll)
        except NoMatches:
            return
        y0, _ = active_band(self.view.active, self._rendered_h)
        sc.scroll_to(y=y0, animate=False)

    def on_resize(self, event) -> None:
        self._draw()

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
        co = self._cfg.colors
        min_h = content_min_height()
        if min_h > vh:
            # Content is taller than the viewport: render its full height (less
            # one column for the scrollbar) so the container can scroll it.
            self._rendered_h = min_h
            frame = render(self.state, (w - 1, min_h), self.view, self.stopwatch, co, self.editor)
        else:
            self._rendered_h = vh
            frame = render(self.state, (w, vh), self.view, self.stopwatch, co, self.editor)

        # Skip the (expensive) ANSI parse + widget update when nothing changed.
        if frame == self._last_frame:
            return
        self._last_frame = frame
        frame_widget.update(Text.from_ansi(frame))


def run(total_seconds: int | None, config: Config | None = None) -> None:
    ClockApp(total_seconds, config=config).run()
