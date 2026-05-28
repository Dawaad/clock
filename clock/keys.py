"""Single source of truth for sections, actions, and key bindings.

Everything key-related derives from :data:`REGISTRY`:

- :mod:`clock.config` builds the user-overridable default keybinds from it.
- :mod:`clock.ui` reads each section's bindings to draw its keybind strip.
- :func:`dispatch` resolves a (focused section, key) pair to an :class:`Action`.

A binding is contextual: the same key (e.g. ``space``) maps to a different
action depending on which section is focused, which is what lets the timer and
the stopwatch share one key without colliding.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class Section(Enum):
    """A focusable panel, plus a GLOBAL pseudo-section for always-on keys."""

    TIMER = "timer"
    STOPWATCH = "stopwatch"
    TIME = "time"
    GLOBAL = "global"


# The order arrow-key navigation cycles through (GLOBAL is not focusable).
FOCUS_ORDER: tuple[Section, ...] = (Section.TIMER, Section.STOPWATCH, Section.TIME)


class Action(Enum):
    PAUSE = "pause"
    ADJUST_UP = "adjust_up"
    ADJUST_DOWN = "adjust_down"
    CLEAR_TIMER = "clear_timer"
    SW_TOGGLE = "sw_toggle"
    SW_RESET = "sw_reset"
    SET_TIMER = "set_timer"
    QUIT = "quit"
    FOCUS_NEXT = "focus_next"
    FOCUS_PREV = "focus_prev"


@dataclass(frozen=True)
class Bind:
    """One binding: an action, its default keys, a strip label, and its owner.

    ``keys`` are Textual key names (the form ``on_key`` sees and config files
    use). ``label`` is the human description shown in a section's keybind strip.
    """

    action: Action
    keys: tuple[str, ...]
    label: str
    section: Section


# Each Action appears exactly once; section ownership is what makes dispatch
# contextual. See the registry invariants in tests/test_keys.py.
REGISTRY: tuple[Bind, ...] = (
    Bind(Action.PAUSE, ("space", "p"), "pause", Section.TIMER),
    Bind(Action.ADJUST_UP, ("plus", "equals_sign"), "+10s", Section.TIMER),
    Bind(Action.ADJUST_DOWN, ("minus", "underscore"), "-10s", Section.TIMER),
    Bind(Action.CLEAR_TIMER, ("c",), "clear", Section.TIMER),
    Bind(Action.SW_TOGGLE, ("space", "p"), "start / pause", Section.STOPWATCH),
    Bind(Action.SW_RESET, ("c",), "reset", Section.STOPWATCH),
    Bind(Action.FOCUS_PREV, ("up", "left"), "prev", Section.GLOBAL),
    Bind(Action.FOCUS_NEXT, ("down", "right"), "next", Section.GLOBAL),
    Bind(Action.SET_TIMER, ("e",), "set timer", Section.GLOBAL),
    Bind(Action.QUIT, ("q",), "quit", Section.GLOBAL),
)

# Action name -> default keys. Mirrors the registry; the canonical default map
# that config merges user overrides into.
DEFAULT_KEYBINDS: dict[str, tuple[str, ...]] = {b.action.value: b.keys for b in REGISTRY}

# Pretty single-key glyphs for the keybind strip.
_GLYPHS = {
    "space": "space",
    "plus": "+",
    "equals_sign": "=",
    "minus": "-",
    "underscore": "_",
    "up": "↑",
    "down": "↓",
    "left": "←",
    "right": "→",
    "escape": "esc",
}


def glyph(key: str) -> str:
    """Display form of a Textual key name for the keybind strip."""
    return _GLYPHS.get(key, key)


def primary_glyph(keys: tuple[str, ...]) -> str:
    """Glyph for the first (primary) key of a binding."""
    return glyph(keys[0]) if keys else ""


def dispatch(
    section: Section,
    key: str,
    keybinds: dict[str, tuple[str, ...]] | None = None,
) -> Action | None:
    """Resolve a key pressed while ``section`` is focused to an action.

    Considers bindings owned by ``section`` and by ``GLOBAL`` (which apply
    regardless of focus). ``keybinds`` overrides the default keys per action;
    unknown keys return ``None``. The registry's no-collision invariant means at
    most one binding matches.
    """
    binds = keybinds if keybinds is not None else DEFAULT_KEYBINDS
    for b in REGISTRY:
        if b.section is section or b.section is Section.GLOBAL:
            if key in binds.get(b.action.value, b.keys):
                return b.action
    return None


def section_binds(section: Section) -> tuple[Bind, ...]:
    """Bindings owned by a section (excludes GLOBAL), in registry order."""
    return tuple(b for b in REGISTRY if b.section is section)


def global_binds() -> tuple[Bind, ...]:
    return tuple(b for b in REGISTRY if b.section is Section.GLOBAL)
