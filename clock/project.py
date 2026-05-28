"""Minimal 3D camera: rotate a model point and perspective-project it.

Coordinate system (model/world):
    +x right, +y up, +z toward the camera.
The camera sits at z = ``distance`` looking toward the origin. A point's
distance from the camera is ``distance - z`` (smaller = nearer), which doubles
as the depth value for z-buffering.

Rotation order is yaw (about +y) then pitch (about +x): yaw spins the puck,
pitch tilts its top away from the viewer.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

Vec3 = tuple[float, float, float]


@dataclass(frozen=True)
class View:
    pitch: float        # radians; tilt top away from viewer
    yaw: float          # radians; spin about the vertical axis
    focal: float        # projection focal length
    distance: float     # camera distance along +z


def rotate(p: Vec3, pitch: float, yaw: float) -> Vec3:
    x, y, z = p
    cy, sy = math.cos(yaw), math.sin(yaw)
    x1 = x * cy + z * sy
    z1 = -x * sy + z * cy
    cx, sx = math.cos(pitch), math.sin(pitch)
    # Positive pitch tilts the top (+y) away from the camera (-z).
    y2 = y * cx + z1 * sx
    z2 = -y * sx + z1 * cx
    return x1, y2, z2


def project(p: Vec3, view: View) -> tuple[float, float, float]:
    """Return (screen_x, screen_y, depth). depth = distance from camera."""
    x, y, z = rotate(p, view.pitch, view.yaw)
    depth = view.distance - z
    if depth < 1e-6:
        depth = 1e-6
    s = view.focal / depth
    return x * s, y * s, depth


def face_normal(view: View) -> Vec3:
    """World-space normal of the face plane (model +z) after rotation."""
    return rotate((0.0, 0.0, 1.0), view.pitch, view.yaw)
