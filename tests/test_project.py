import math

from clock.project import View, face_normal, project, rotate

VIEW = View(pitch=0.0, yaw=0.0, focal=100.0, distance=10.0)


def approx(a, b, tol=1e-6):
    return abs(a - b) <= tol


def test_rotate_identity():
    assert rotate((1, 2, 3), 0, 0) == (1, 2, 3)


def test_yaw_90_maps_x_to_negative_z():
    x, y, z = rotate((1, 0, 0), 0, math.pi / 2)
    assert approx(x, 0, 1e-9)
    assert approx(z, -1, 1e-9)


def test_pitch_90_tilts_top_away():
    # Positive pitch swings the top (+y) to far depth (-z).
    x, y, z = rotate((0, 1, 0), math.pi / 2, 0)
    assert approx(y, 0, 1e-9)
    assert approx(z, -1, 1e-9)


def test_project_centre_point():
    sx, sy, depth = project((0, 0, 0), VIEW)
    assert (sx, sy) == (0, 0)
    assert approx(depth, 10.0)


def test_project_nearer_point_is_bigger():
    # A point closer to the camera (larger z) projects to a larger radius.
    far = project((1, 0, -2), VIEW)
    near = project((1, 0, 2), VIEW)
    assert near[0] > far[0]
    assert near[2] < far[2]  # nearer => smaller depth


def test_face_normal_points_at_camera_when_flat():
    assert face_normal(VIEW) == (0.0, 0.0, 1.0)


def test_face_normal_tilts_with_pitch():
    nx, ny, nz = face_normal(View(pitch=0.5, yaw=0.0, focal=100, distance=10))
    assert nz < 1.0          # tilted away from straight-on
    assert ny > 0.0          # top tips toward +y in world
