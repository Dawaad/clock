import pytest

from clock.config import (
    DEFAULT_KEYBINDS,
    Colors,
    Config,
    ConfigError,
    load_config,
)
from clock import theme


@pytest.fixture(autouse=True)
def isolate_config(tmp_path, monkeypatch):
    # Point discovery at an empty dir so a real ~/.config/clock does not leak in.
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    return tmp_path


def write(tmp_path, body):
    p = tmp_path / "clock" / "config.toml"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(body)
    return p


def test_defaults_match_theme():
    cfg = load_config()
    assert cfg.colors == Colors()
    assert cfg.colors.bg == theme.BG
    assert dict(cfg.keybinds) == DEFAULT_KEYBINDS


def test_user_colors_override(isolate_config):
    write(isolate_config, '[colors]\nbg = "#101012"\naccent = "#ff8800"\n')
    cfg = load_config()
    assert cfg.colors.bg == (16, 16, 18)
    assert cfg.colors.accent == (255, 136, 0)
    assert cfg.colors.ink == theme.INK  # untouched keys keep defaults


def test_keybinds_override_and_accept_scalar(isolate_config):
    write(isolate_config, '[keybinds]\nquit = ["q", "escape"]\nset_timer = "t"\n')
    cfg = load_config()
    assert cfg.keybinds["quit"] == ("q", "escape")
    assert cfg.keybinds["set_timer"] == ("t",)
    assert cfg.keybinds["pause"] == DEFAULT_KEYBINDS["pause"]


def test_explicit_path_takes_precedence(tmp_path):
    custom = tmp_path / "mine.toml"
    custom.write_text('[colors]\nink = "#abcdef"\n')
    cfg = load_config(custom)
    assert cfg.colors.ink == (0xAB, 0xCD, 0xEF)


def test_missing_explicit_path_errors():
    with pytest.raises(ConfigError, match="not found"):
        load_config("/no/such/config.toml")


def test_bad_hex_errors(isolate_config):
    write(isolate_config, '[colors]\nbg = "nope"\n')
    with pytest.raises(ConfigError, match="invalid color"):
        load_config()


def test_unknown_color_key_errors(isolate_config):
    write(isolate_config, '[colors]\nfuchsia = "#ffffff"\n')
    with pytest.raises(ConfigError, match="unknown color"):
        load_config()


def test_unknown_action_errors(isolate_config):
    write(isolate_config, '[keybinds]\nlevitate = "z"\n')
    with pytest.raises(ConfigError, match="unknown action"):
        load_config()


def test_malformed_toml_errors(isolate_config):
    write(isolate_config, "this is = = not toml")
    with pytest.raises(ConfigError):
        load_config()
