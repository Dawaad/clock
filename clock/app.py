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
from textual.containers import Horizontal, VerticalScroll, Vertical
from textual.css.query import NoMatches
from textual.screen import ModalScreen
from textual.widgets import Input, Label, Static

from .config import Config
from .parse import DurationError, parse_duration
from .state import Stopwatch, advance, apply_key, new_timer, sw_tick, sw_toggle, with_now
from .ui import STACK_MIN_H, is_narrow, render

_SCROLL_KEYS = {"up", "down", "pageup", "pagedown", "home", "end"}

# Adjustment actions -> the token the state reducer understands.
_ACTION_TOKENS = {"pause": " ", "adjust_up": "+", "adjust_down": "-"}

DEFAULT_FPS = 10
FINISH_BELLS = 4
FINISH_LINGER = 2.0


class DurationModal(ModalScreen[int | None]):
    """A rofi-style centered prompt for entering a countdown duration.

    Dismisses with the parsed seconds on submit, or ``None`` on cancel.
    """

    CSS = """
    DurationModal { align: center middle; }
    #dialog {
        width: 56; height: auto;
        background: rgb(237,234,226);
        border: round rgb(203,200,192);
        padding: 1 2;
    }
    #prompt { height: 3; }
    #chip {
        background: rgb(198,72,56); color: rgb(237,234,226);
        padding: 0 1; margin: 1 2 0 0; text-style: bold;
    }
    #dur {
        background: rgb(237,234,226); color: rgb(30,30,32);
        border: tall rgb(203,200,192); height: 3;
    }
    #dur:focus { border: tall rgb(198,72,56); }
    #error { color: rgb(198,72,56); height: 1; }
    #hint { color: rgb(138,136,130); height: 1; }
    """

    BINDINGS = [("escape", "cancel", "cancel")]

    def compose(self) -> ComposeResult:
        with Vertical(id="dialog"):
            with Horizontal(id="prompt"):
                yield Label("TIMER", id="chip")
                yield Input(placeholder="e.g. 5m, 30:00, 90s, 1h30m", id="dur")
            yield Label("", id="error")
            yield Label("[enter] start    [esc] cancel", id="hint")

    def on_mount(self) -> None:
        self.query_one("#dur", Input).focus()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        try:
            total = parse_duration(event.value)
        except DurationError as exc:
            self.query_one("#error", Label).update(str(exc))
            return
        self.dismiss(total)

    def action_cancel(self) -> None:
        self.dismiss(None)


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
        # Flatten {action: keys} into {key: action} for O(1) dispatch on input.
        self._actions = {
            key: action
            for action, keys in self._cfg.keybinds.items()
            for key in keys
        }

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
        key = event.key
        action = self._actions.get(key)
        if action == "quit":
            self.exit()
            return
        if action == "set_timer":
            self._open_picker()
            return
        if key == "s":
            self.stopwatch = sw_toggle(self.stopwatch)
            self._draw()
            return
        if key == "c" and (self._configured or self._stopwatch_active()):
            self._clear()
            return
        if key in _SCROLL_KEYS:
            self._scroll(key)
            return
        token = _KEY_MAP.get(key)
        token = _ACTION_TOKENS.get(action)
        if token is not None:
            self.state = apply_key(self.state, token)
            self._draw()
            return
        if key in _SCROLL_KEYS:
            self._scroll(key)

    def _open_picker(self) -> None:
        self.push_screen(DurationModal(), self._on_duration_chosen)

    def _stopwatch_active(self) -> bool:
        return self.stopwatch.running or self.stopwatch.elapsed > 0

    def _clear(self) -> None:
        self.state = new_timer(0, self._wallclock())
        self._configured = False
        self._alerted = False
        self.stopwatch = Stopwatch()
        self._draw()

    def _on_duration_chosen(self, total: int | None) -> None:
        if total is None:
            # Cancelled: fall back to (or keep) the default blank-timer view.
            return
        self.state = new_timer(total, self._wallclock())
        self._configured = True
        self._alerted = False
        self._last = self._monotonic()
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
        co = self._cfg.colors
        if is_narrow(w) and STACK_MIN_H > vh:
            # Stacked content is taller than the viewport: render its full height
            # (less one column for the scrollbar) so the container can scroll it.
            frame = render(self.state, (w - 1, STACK_MIN_H), self.stopwatch, co)            
        else:
            frame = render(self.state, (w, vh), self.stopwatch, co)

        frame_widget.update(Text.from_ansi(frame))


def run(total_seconds: int | None, config: Config | None = None) -> None:
    ClockApp(total_seconds, config=config).run()
