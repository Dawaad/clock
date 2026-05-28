"""Registry invariants (11A) and dispatch resolution (10A)."""

from collections import Counter

import pytest

from clock.keys import (
    DEFAULT_KEYBINDS,
    FOCUS_ORDER,
    REGISTRY,
    Action,
    Section,
    dispatch,
    global_binds,
    primary_glyph,
    section_binds,
)

FOCUSABLE = [Section.TIMER, Section.STOPWATCH, Section.TIME]


# --------------------------------------------------------------------------- #
# Registry invariants (11A)
# --------------------------------------------------------------------------- #

def test_each_action_bound_exactly_once():
    counts = Counter(b.action for b in REGISTRY)
    dupes = {a: n for a, n in counts.items() if n > 1}
    assert not dupes, f"actions bound more than once: {dupes}"


def test_every_action_is_reachable():
    bound = {b.action for b in REGISTRY}
    assert bound == set(Action), f"unreachable actions: {set(Action) - bound}"


def test_no_duplicate_key_within_a_section():
    # A key resolves to one action per focus context: within a section's own
    # bindings plus GLOBAL, no key may appear twice.
    for section in FOCUSABLE:
        keys: list[str] = []
        for b in REGISTRY:
            if b.section is section or b.section is Section.GLOBAL:
                keys.extend(b.keys)
        dupes = [k for k, n in Counter(keys).items() if n > 1]
        assert not dupes, f"{section} has colliding keys: {dupes}"


def test_global_keys_never_collide_with_section_keys():
    global_keys = {k for b in global_binds() for k in b.keys}
    for b in REGISTRY:
        if b.section is not Section.GLOBAL:
            overlap = global_keys & set(b.keys)
            assert not overlap, f"{b.action} shares keys with GLOBAL: {overlap}"


def test_default_keybinds_mirror_registry():
    assert DEFAULT_KEYBINDS == {b.action.value: b.keys for b in REGISTRY}


def test_focus_order_is_focusable_sections_only():
    assert set(FOCUS_ORDER) == set(FOCUSABLE)
    assert Section.GLOBAL not in FOCUS_ORDER


# --------------------------------------------------------------------------- #
# dispatch (10A)
# --------------------------------------------------------------------------- #

def test_space_is_contextual():
    assert dispatch(Section.TIMER, "space") is Action.PAUSE
    assert dispatch(Section.STOPWATCH, "space") is Action.SW_TOGGLE
    # TIME has no space binding of its own and space is not GLOBAL.
    assert dispatch(Section.TIME, "space") is None


def test_adjust_keys_resolve_only_under_timer():
    for key in ("plus", "equals_sign", "minus", "underscore"):
        assert dispatch(Section.TIMER, key) is not None
        assert dispatch(Section.STOPWATCH, key) is None
        assert dispatch(Section.TIME, key) is None


def test_clear_is_contextual():
    assert dispatch(Section.TIMER, "c") is Action.CLEAR_TIMER
    assert dispatch(Section.STOPWATCH, "c") is Action.SW_RESET
    assert dispatch(Section.TIME, "c") is None


@pytest.mark.parametrize("section", FOCUSABLE)
def test_global_keys_resolve_from_any_section(section):
    assert dispatch(section, "q") is Action.QUIT
    assert dispatch(section, "e") is Action.SET_TIMER
    assert dispatch(section, "down") is Action.FOCUS_NEXT
    assert dispatch(section, "up") is Action.FOCUS_PREV
    assert dispatch(section, "right") is Action.FOCUS_NEXT
    assert dispatch(section, "left") is Action.FOCUS_PREV


@pytest.mark.parametrize("section", FOCUSABLE)
def test_unknown_key_returns_none(section):
    assert dispatch(section, "z") is None


def test_user_override_changes_resolution():
    binds = {**DEFAULT_KEYBINDS, "quit": ("x",)}
    assert dispatch(Section.TIMER, "x", binds) is Action.QUIT
    assert dispatch(Section.TIMER, "q", binds) is None


def test_section_binds_excludes_global():
    for b in section_binds(Section.TIMER):
        assert b.section is Section.TIMER
    assert {b.action for b in section_binds(Section.STOPWATCH)} == {
        Action.SW_TOGGLE,
        Action.SW_RESET,
    }
    assert section_binds(Section.TIME) == ()


def test_primary_glyph():
    assert primary_glyph(("space", "p")) == "space"
    assert primary_glyph(("plus", "equals_sign")) == "+"
    assert primary_glyph(()) == ""
