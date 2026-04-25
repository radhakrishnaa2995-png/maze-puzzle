"""Shape utilities for masked maze generation."""

from __future__ import annotations

import math
import random
from typing import Callable, Iterable, List

SHAPES = [
    "Square",
    "Circle",
    "Triangle",
    "Star",
    "Heart",
    "Hexagon",
    "Oval",
    "Spiral",
    "Diamond",
    "Rectangle",
]


MaskFn = Callable[[float, float], bool]


def _regular_polygon_mask(sides: int, radius: float = 0.9, rotation: float = 0.0) -> MaskFn:
    vertices = [
        (
            radius * math.cos(rotation + (2 * math.pi * i / sides)),
            radius * math.sin(rotation + (2 * math.pi * i / sides)),
        )
        for i in range(sides)
    ]

    def mask(x: float, y: float) -> bool:
        inside = False
        j = len(vertices) - 1
        for i, (xi, yi) in enumerate(vertices):
            xj, yj = vertices[j]
            if (yi > y) != (yj > y):
                x_inter = (xj - xi) * (y - yi) / (yj - yi + 1e-9) + xi
                if x < x_inter:
                    inside = not inside
            j = i
        return inside

    return mask


def _star_mask(x: float, y: float) -> bool:
    points: List[tuple[float, float]] = []
    for i in range(10):
        angle = -math.pi / 2 + i * math.pi / 5
        r = 0.95 if i % 2 == 0 else 0.42
        points.append((r * math.cos(angle), r * math.sin(angle)))

    inside = False
    j = len(points) - 1
    for i, (xi, yi) in enumerate(points):
        xj, yj = points[j]
        if (yi > y) != (yj > y):
            x_inter = (xj - xi) * (y - yi) / (yj - yi + 1e-9) + xi
            if x < x_inter:
                inside = not inside
        j = i
    return inside


def _heart_mask(x: float, y: float) -> bool:
    sx = x * 1.25
    sy = y * 1.25
    value = (sx * sx + sy * sy - 1) ** 3 - sx * sx * sy**3
    return value <= 0 and sy <= 0.95


def _triangle_mask(x: float, y: float) -> bool:
    # Upright equilateral-like triangle
    if y < -0.85 or y > 0.85:
        return False
    half_width = (0.85 - y) * 0.9
    return -half_width <= x <= half_width


def _diamond_mask(x: float, y: float) -> bool:
    return abs(x) / 0.85 + abs(y) / 0.9 <= 1


def _oval_mask(x: float, y: float) -> bool:
    return (x * x) / (0.92 * 0.92) + (y * y) / (0.72 * 0.72) <= 1


def _rectangle_mask(x: float, y: float) -> bool:
    return abs(x) <= 0.92 and abs(y) <= 0.66


def _square_mask(x: float, y: float) -> bool:
    return abs(x) <= 0.84 and abs(y) <= 0.84


def _circle_mask(x: float, y: float) -> bool:
    return x * x + y * y <= 0.86 * 0.86


def _hexagon_mask() -> MaskFn:
    return _regular_polygon_mask(6, radius=0.9, rotation=math.pi / 6)


def _spiral_mask(x: float, y: float) -> bool:
    r = math.hypot(x, y)
    if r < 0.12 or r > 0.92:
        return False
    theta = math.atan2(y, x)
    if theta < 0:
        theta += 2 * math.pi

    # Three-quarters turn spiral ribbon with finite width
    arm_theta = theta + (2 * math.pi if theta < math.pi / 2 else 0)
    target_r = 0.9 - 0.12 * arm_theta
    return abs(r - target_r) < 0.18


MASK_BUILDERS: dict[str, Callable[..., MaskFn] | MaskFn] = {
    "Square": _square_mask,
    "Circle": _circle_mask,
    "Triangle": _triangle_mask,
    "Star": _star_mask,
    "Heart": _heart_mask,
    "Hexagon": _hexagon_mask,
    "Oval": _oval_mask,
    "Spiral": _spiral_mask,
    "Diamond": _diamond_mask,
    "Rectangle": _rectangle_mask,
}


def mask_for_shape(shape_name: str) -> MaskFn:
    builder = MASK_BUILDERS[shape_name]
    if callable(builder) and shape_name == "Hexagon":
        return builder()  # type: ignore[misc]
    return builder  # type: ignore[return-value]


def shape_sequence(total_pages: int, rng: random.Random) -> List[str]:
    """Create a varied random shape order without long same-shape runs."""
    sequence: List[str] = []
    bag = SHAPES.copy()

    while len(sequence) < total_pages:
        rng.shuffle(bag)
        for shape in bag:
            if len(sequence) >= total_pages:
                break
            if sequence and sequence[-1] == shape:
                continue
            sequence.append(shape)

    return sequence


def palette_sequence(total_pages: int, palettes: Iterable[str], rng: random.Random) -> List[str]:
    colors = list(palettes)
    if not colors:
        return []

    sequence: List[str] = []
    while len(sequence) < total_pages:
        rng.shuffle(colors)
        sequence.extend(colors)
    return sequence[:total_pages]
