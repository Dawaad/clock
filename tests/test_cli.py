import pytest

from clock.cli import _build_parser, main


def test_duration_argument_is_optional():
    # Omitting the duration is allowed; the app then prompts for one.
    assert _build_parser().parse_args([]).duration is None


def test_missing_argument_does_not_error():
    # No duration is no longer a usage error; non-tty refusal returns 1 instead.
    assert main([]) == 1


def test_invalid_duration_errors():
    with pytest.raises(SystemExit) as exc:
        main(["nonsense"])
    assert exc.value.code == 2


def test_version_exits_zero():
    with pytest.raises(SystemExit) as exc:
        main(["--version"])
    assert exc.value.code == 0


def test_non_tty_refuses(capsys):
    # pytest captures stdout, so it is not a tty here.
    rc = main(["30"])
    assert rc == 1
    assert "interactive terminal" in capsys.readouterr().err
