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
from textual.containers import Horizontal, VerticalScroll, Vertical
from textual.css.query import NoMatches
from textual.screen import ModalScreen
from textual.widgets import Input, Label, Static

from .config import Colors, Config
from .parse import DurationError, parse_duration
from .state import advance, apply_key, new_timer, with_now
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

    # Layout only; colors are applied from the active palette in on_mount so the
    # prompt matches whatever --theme is in effect.
    CSS = """
    DurationModal { align: center middle; }
    #dialog { width: 56; height: auto; padding: 1 2; }
    #prompt { height: 3; }
    #chip { padding: 0 1; margin: 1 2 0 0; text-style: bold; }
    #dur { height: 3; }
    #error { height: 1; }
    #hint { height: 1; }
    """

    BINDINGS = [("escape", "cancel", "cancel")]

    def __init__(self, colors: Colors) -> None:
        super().__init__()
        self._co = colors

    def compose(self) -> ComposeResult:
        with Vertical(id="dialog"):
            with Horizontal(id="prompt"):
                yield Label("TIMER", id="chip")
                yield Input(placeholder="e.g. 5m, 30:00, 90s, 1h30m", id="dur")
            yield Label("", id="error")
            yield Label("[enter] start    [esc] cancel", id="hint")

    def on_mount(self) -> None:
        co = self._co
        bg, ink, soft = Color(*co.bg), Color(*co.ink), Color(*co.ink_soft)
        faint, accent = Color(*co.faint), Color(*co.accent)
        dialog = self.query_one("#dialog")
        dialog.styles.background = bg
        dialog.styles.border = ("round", faint)
        chip = self.query_one("#chip")
        chip.styles.background = accent
        chip.styles.color = bg
        inp = self.query_one("#dur", Input)
        inp.styles.background = bg
        inp.styles.color = ink
        inp.styles.border = ("tall", faint)
        self.query_one("#error", Label).styles.color = accent
        self.query_one("#hint", Label).styles.color = soft
        inp.focus()

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
        self.screen.styles.background = Color(*self._cfg.colors.bg)
        self._last = self._monotonic()
        self.set_interval(1 / self._fps, self._tick)
        self._draw()
        if not self._configured:
            self._open_picker()

    def _tick(self) -> None:
        now = self._monotonic()
        dt, self._last = now - self._last, now
        if not self._configured:
            # No duration chosen yet: keep the wall clock live but hold the
            # countdown so it neither advances nor fires the finish alert.
            self.state = with_now(self.state, self._wallclock())
            self._draw()
            return
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
        action = self._actions.get(key)
        if action == "quit":
            self.exit()
            return
        if action == "set_timer":
            self._open_picker()
            return
        token = _ACTION_TOKENS.get(action)
        if token is not None:
            self.state = apply_key(self.state, token)
            self._draw()
            return
        if key in _SCROLL_KEYS:
            self._scroll(key)

    def _open_picker(self) -> None:
        self.push_screen(DurationModal(self._cfg.colors), self._on_duration_chosen)

    def _on_duration_chosen(self, total: int | None) -> None:
        if total is None:
            # Cancelled with no timer ever set: nothing to show, so quit.
            if not self._configured:
                self.exit()
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
            frame = render(self.state, (w - 1, STACK_MIN_H), co)
        else:
            frame = render(self.state, (w, vh), co)
        frame_widget.update(Text.from_ansi(frame))


def run(total_seconds: int | None, config: Config | None = None) -> None:
    ClockApp(total_seconds, config=config).run()
