import pytest

from clock.cli import main


def test_missing_argument_errors():
    with pytest.raises(SystemExit) as exc:
        main([])
    assert exc.value.code == 2


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
