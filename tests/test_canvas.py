import math

from clock.canvas import Canvas, draw_arc, emit_grid, radial_ticks, vertical_ticks


def test_dot_blends_same_layer():
    c = Canvas(2, 1)
    c.dot(0, 0, (200, 0, 0), layer=0)
    c.dot(1, 0, (0, 200, 0), layer=0)  # same braille cell, same layer
    grid = [[None, None]]
    c.blit_into(grid)
    ch, color = grid[0][0]
    assert color == (100, 100, 0)  # averaged


def test_dot_higher_layer_wins():
    c = Canvas(2, 1)
    c.dot(0, 0, (200, 0, 0), layer=0)
    c.dot(0, 0, (0, 0, 200), layer=1)
    grid = [[None, None]]
    c.blit_into(grid)
    _, color = grid[0][0]
    assert color == (0, 0, 200)


def test_dot_out_of_bounds_ignored():
    c = Canvas(1, 1)
    c.dot(-1, 0, (255, 255, 255))
    c.dot(100, 100, (255, 255, 255))
    assert c.bits == {}


def test_draw_arc_places_dots():
    c = Canvas(40, 40)
    draw_arc(c, 40, 80, 30, 2, 0, 2 * math.pi, (255, 0, 0), layer=0)
    assert len(c.bits) > 0


def test_radial_and_vertical_ticks_place_dots():
    c = Canvas(40, 40)
    radial_ticks(c, 40, 80, 28, 32, 12, (100, 100, 100))
    n_radial = len(c.bits)
    assert n_radial > 0
    vertical_ticks(c, 70, 10, 150, 10, 5, 2, 5, (100, 100, 100))
    assert len(c.bits) > n_radial


def test_emit_coalesces_same_color_runs():
    red = (255, 0, 0)
    grid = [[("a", red), ("b", red), ("c", red)]]
    line = emit_grid(grid)
    # One colour escape for the run, one reset at the row end.
    assert line.count("\033[38;2;255;0;0m") == 1
    assert line.endswith("\033[0m")
    assert "abc" in line


def test_emit_resets_on_blank():
    red = (255, 0, 0)
    grid = [[("a", red), None, ("b", red)]]
    line = emit_grid(grid)
    assert line.count("\033[38;2;255;0;0m") == 2  # colour re-emitted after blank
    assert "\033[0m" in line


def test_emit_blank_only_row():
    assert emit_grid([[None, None]]) == "  "
