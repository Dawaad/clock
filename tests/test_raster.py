from clock.raster import DEFAULT_BG, DEFAULT_FG, Frame


def test_surface_nearest_wins():
    f = Frame(1, 1)
    f.surface(0, 0, 5.0, bg=(10, 10, 10))
    f.surface(0, 0, 2.0, bg=(20, 20, 20))   # nearer
    f.surface(0, 0, 9.0, bg=(30, 30, 30))   # farther, ignored
    assert f.bg[0][0] == (20, 20, 20)
    assert f.z[0][0] == 2.0


def test_set_bg_ignores_depth():
    f = Frame(1, 1)
    f.surface(0, 0, 1.0, bg=(20, 20, 20))
    f.set_bg(0, 0, (5, 5, 5))
    assert f.bg[0][0] == (5, 5, 5)


def test_overlay_respects_occlusion():
    f = Frame(1, 1)
    f.surface(0, 0, 2.0, bg=(255, 255, 255))   # face at depth 2
    f.overlay(0, 0, 9.0, "#", (0, 0, 0))        # behind the face -> hidden
    assert f.char[0][0] == " "
    f.overlay(0, 0, 2.0, "#", (0, 0, 0))        # on the face -> shown
    assert f.char[0][0] == "#"


def test_emit_uses_defaults_and_resets():
    f = Frame(2, 1)
    line = f.emit()
    assert line.endswith("\033[0m")
    assert f"38;2;{DEFAULT_FG[0]}" in line
    assert f"48;2;{DEFAULT_BG[0]}" in line


def test_emit_coalesces_runs():
    f = Frame(3, 1)
    for x in range(3):
        f.surface(x, 0, 1.0, bg=(100, 0, 0), fg=(0, 0, 0), char="x")
    line = f.emit()
    assert line.count("48;2;100;0;0") == 1
    assert "xxx" in line
