from clock.raster import DEFAULT_BG, DEFAULT_FG, Frame


def test_put_sets_char_and_fg():
    f = Frame(2, 1)
    f.put(1, 0, "x", (10, 20, 30))
    assert f.char[0][1] == "x"
    assert f.fg[0][1] == (10, 20, 30)


def test_put_out_of_bounds_ignored():
    f = Frame(1, 1)
    f.put(5, 5, "x", (0, 0, 0))   # no error, no write
    assert f.char[0][0] == " "


def test_text_writes_string():
    f = Frame(5, 1)
    f.text(0, 0, "hi", (0, 0, 0))
    assert "".join(f.char[0]).rstrip() == "hi"


def test_fill_bg():
    f = Frame(2, 2)
    f.fill_bg((1, 2, 3))
    assert all(f.bg[y][x] == (1, 2, 3) for y in range(2) for x in range(2))


def test_emit_uses_defaults_and_resets():
    line = Frame(2, 1).emit()
    assert line.endswith("\033[0m")
    assert f"38;2;{DEFAULT_FG[0]}" in line
    assert f"48;2;{DEFAULT_BG[0]}" in line


def test_emit_coalesces_runs():
    f = Frame(3, 1)
    for x in range(3):
        f.put(x, 0, "x", (0, 0, 0), bg=(100, 0, 0))
    line = f.emit()
    assert line.count("48;2;100;0;0") == 1
    assert "xxx" in line
