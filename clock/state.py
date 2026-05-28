"""Immutable timer state and pure transitions.

The state is a frozen snapshot; transitions return new instances so they are
trivial to unit-test. The app layer owns the real clocks and feeds them in:

- ``advance(state, dt)`` moves the countdown by a monotonic delta.
- ``with_now(state, now)`` stamps the current wall time (used by the header).
- ``toggle_pause(state)`` / ``adjust(state, delta)`` are the timer controls.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime

from .keys import FOCUS_ORDER, Section

DEFAULT_STEP = 10


@dataclass(frozen=True)
class TimerState:
    total_seconds: int          # denominator for the progress fraction
    remaining: float            # seconds left
    now: datetime               # current wall time (for the header)
    paused: bool = False

    @property
    def finished(self) -> bool:
        return self.remaining <= 0

    @property
    def elapsed(self) -> float:
        return max(0.0, self.total_seconds - self.remaining)

    @property
    def fraction(self) -> float:
        """Portion of time remaining, clamped to [0, 1]."""
        if self.total_seconds <= 0:
            return 0.0
        return max(0.0, min(1.0, self.remaining / self.total_seconds))


def new_timer(total_seconds: int, now: datetime) -> TimerState:
    return TimerState(
        total_seconds=total_seconds,
        remaining=float(total_seconds),
        now=now,
    )


def advance(state: TimerState, dt: float) -> TimerState:
    """Move the countdown forward by ``dt`` seconds of real time."""
    if state.paused or state.finished or dt <= 0:
        return state
    return replace(state, remaining=max(0.0, state.remaining - dt))


def with_now(state: TimerState, now: datetime) -> TimerState:
    return replace(state, now=now)


@dataclass(frozen=True)
class Stopwatch:
    """A count-up timer, independent of the countdown."""

    elapsed: float = 0.0
    running: bool = False


def sw_toggle(sw: Stopwatch) -> Stopwatch:
    """Start, pause, or resume the stopwatch."""
    return replace(sw, running=not sw.running)


def sw_tick(sw: Stopwatch, dt: float) -> Stopwatch:
    """Add ``dt`` seconds of real time while running."""
    if not sw.running or dt <= 0:
        return sw
    return replace(sw, elapsed=sw.elapsed + dt)


def sw_reset(sw: Stopwatch) -> Stopwatch:
    """Stop and zero the stopwatch."""
    return Stopwatch()


def toggle_pause(state: TimerState) -> TimerState:
    return replace(state, paused=not state.paused)


def adjust(state: TimerState, delta: float) -> TimerState:
    """Add ``delta`` seconds to the remaining time (clamped at zero).

    A positive adjustment also grows ``total_seconds`` so the progress fraction
    never exceeds 1; a negative one leaves the denominator untouched.
    """
    remaining = max(0.0, state.remaining + delta)
    total = max(state.total_seconds, int(round(remaining)))
    return replace(state, remaining=remaining, total_seconds=total)


@dataclass(frozen=True)
class View:
    """Which section currently has focus (the one key context acts on)."""

    active: Section = Section.TIMER


@dataclass(frozen=True)
class Editor:
    """Inline duration entry shown in the TIMER section (replaces the modal)."""

    active: bool = False
    buffer: str = ""
    error: str | None = None


def focus_next(view: View) -> View:
    i = FOCUS_ORDER.index(view.active)
    return replace(view, active=FOCUS_ORDER[(i + 1) % len(FOCUS_ORDER)])


def focus_prev(view: View) -> View:
    i = FOCUS_ORDER.index(view.active)
    return replace(view, active=FOCUS_ORDER[(i - 1) % len(FOCUS_ORDER)])
