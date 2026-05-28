"""User configuration: colors and keybinds, merged from TOML files.

Discovery precedence (lowest to highest priority):

    built-in defaults
    /etc/clock/config.toml                       (system)
    $XDG_CONFIG_HOME/clock/config.toml           (user; ~/.config fallback)
    an explicit --config path
    runtime overrides (CLI flags)

Everything is optional; an absent file or key falls back to the default, so
``load_config()`` with no files present reproduces the hardcoded look exactly.

Example ``config.toml``::

    [colors]
    bg = "#1e1e20"
    ink = "#edeae2"
    accent = "#c64838"

    [keybinds]
    pause = ["space", "p"]
    quit = ["q", "escape"]
"""

from __future__ import annotations

import os
import tomllib
from dataclasses import dataclass, field, fields, replace
from pathlib import Path
from typing import Mapping

from . import theme
from .theme import RGB

# Action -> default Textual key names. Actions are the stable contract that the
# app dispatches on; users remap which keys trigger them.
DEFAULT_KEYBINDS: dict[str, tuple[str, ...]] = {
    "pause": ("space", "p"),
    "adjust_up": ("plus", "equals_sign"),
    "adjust_down": ("minus", "underscore"),
    "set_timer": ("e",),
    "quit": ("q",),
}


class ConfigError(ValueError):
    """Raised when a config file is present but malformed."""


@dataclass(frozen=True)
class Colors:
    bg: RGB = theme.BG
    ink: RGB = theme.INK
    ink_soft: RGB = theme.INK_SOFT
    faint: RGB = theme.FAINT
    accent: RGB = theme.ACCENT


# Ready-to-go palettes, rofi-style. "cream" is the shipped default; a user
# picks another with --theme NAME or `theme = "..."` and may still override
# individual colors via the [colors] table.
DEFAULT_THEME = "cream"

BUILTIN_THEMES: dict[str, Colors] = {
    "cream": Colors(),
    "dark": Colors(
        bg=(24, 24, 27), ink=(235, 235, 232), ink_soft=(140, 140, 145),
        faint=(60, 60, 66), accent=(220, 120, 90),
    ),
    "gruvbox": Colors(
        bg=(40, 40, 40), ink=(235, 219, 178), ink_soft=(168, 153, 132),
        faint=(80, 73, 69), accent=(251, 73, 52),
    ),
    "solarized-dark": Colors(
        bg=(0, 43, 54), ink=(147, 161, 161), ink_soft=(88, 110, 117),
        faint=(7, 54, 66), accent=(203, 75, 22),
    ),
    "solarized-light": Colors(
        bg=(253, 246, 227), ink=(101, 123, 131), ink_soft=(147, 161, 161),
        faint=(238, 232, 213), accent=(203, 75, 22),
    ),
    "nord": Colors(
        bg=(46, 52, 64), ink=(236, 239, 244), ink_soft=(123, 136, 161),
        faint=(76, 86, 106), accent=(191, 97, 106),
    ),
    "matrix": Colors(
        bg=(10, 12, 10), ink=(120, 230, 140), ink_soft=(60, 130, 80),
        faint=(30, 60, 40), accent=(180, 255, 180),
    ),
}


def theme_names() -> list[str]:
    return list(BUILTIN_THEMES)


@dataclass(frozen=True)
class Config:
    colors: Colors = field(default_factory=Colors)
    keybinds: Mapping[str, tuple[str, ...]] = field(
        default_factory=lambda: dict(DEFAULT_KEYBINDS)
    )


def _parse_hex(value: str) -> RGB:
    s = value.strip().lstrip("#")
    if len(s) != 6 or not all(c in "0123456789abcdefABCDEF" for c in s):
        raise ConfigError(f"invalid color {value!r}; expected hex like #1e1e20")
    return (int(s[0:2], 16), int(s[2:4], 16), int(s[4:6], 16))


def _build_colors(data: object, base: Colors) -> Colors:
    if not isinstance(data, dict):
        raise ConfigError("[colors] must be a table")
    known = {f.name for f in fields(Colors)}
    overrides: dict[str, RGB] = {}
    for key, value in data.items():
        if key not in known:
            raise ConfigError(f"unknown color {key!r}; valid: {sorted(known)}")
        overrides[key] = _parse_hex(value)
    return replace(base, **overrides)


def _build_keybinds(data: object) -> dict[str, tuple[str, ...]]:
    if not isinstance(data, dict):
        raise ConfigError("[keybinds] must be a table")
    binds = dict(DEFAULT_KEYBINDS)
    for action, keys in data.items():
        if action not in DEFAULT_KEYBINDS:
            raise ConfigError(
                f"unknown action {action!r}; valid: {sorted(DEFAULT_KEYBINDS)}"
            )
        if isinstance(keys, str):
            keys = [keys]
        if not isinstance(keys, list) or not all(isinstance(k, str) for k in keys):
            raise ConfigError(f"keybind {action!r} must be a string or list of strings")
        binds[action] = tuple(keys)
    return binds


def _resolve_theme(data: dict, override: str | None) -> Colors:
    name = override or data.get("theme") or DEFAULT_THEME
    if not isinstance(name, str):
        raise ConfigError("theme must be a string")
    if name not in BUILTIN_THEMES:
        raise ConfigError(
            f"unknown theme {name!r}; available: {sorted(BUILTIN_THEMES)}"
        )
    return BUILTIN_THEMES[name]


def _config_from_dict(data: dict, theme_override: str | None) -> Config:
    base = _resolve_theme(data, theme_override)
    colors = _build_colors(data["colors"], base) if "colors" in data else base
    keybinds = _build_keybinds(data["keybinds"]) if "keybinds" in data else dict(
        DEFAULT_KEYBINDS
    )
    return Config(colors=colors, keybinds=keybinds)


def _user_config_dir() -> Path:
    base = os.environ.get("XDG_CONFIG_HOME") or os.path.expanduser("~/.config")
    return Path(base) / "clock"


def _discover_paths(explicit: Path | None) -> list[Path]:
    paths = [Path("/etc/clock/config.toml"), _user_config_dir() / "config.toml"]
    if explicit is not None:
        paths.append(explicit)
    return paths


def load_config(
    path: Path | str | None = None,
    theme: str | None = None,
) -> Config:
    """Merge config files in precedence order into a single :class:`Config`.

    ``theme`` is a CLI-level override that wins over a file's ``theme`` key.
    """
    explicit = Path(path) if path is not None else None
    if explicit is not None and not explicit.is_file():
        raise ConfigError(f"config file not found: {explicit}")

    merged: dict = {}
    for p in _discover_paths(explicit):
        if not p.is_file():
            continue
        try:
            data = tomllib.loads(p.read_text())
        except (OSError, tomllib.TOMLDecodeError) as exc:
            raise ConfigError(f"could not read {p}: {exc}") from exc
        # Section-level merge is enough: later files replace whole tables.
        merged.update(data)
    return _config_from_dict(merged, theme)
