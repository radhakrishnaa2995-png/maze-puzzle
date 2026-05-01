"""Geometry-driven maze rendering helpers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Tuple

from maze_generator import Maze

Cell = Tuple[int, int]


@dataclass(frozen=True)
class MazeGeometry:
    cell_size: float
    offset_x: float
    offset_y: float
    min_row: int
    min_col: int
    max_row: int
    max_col: int
    maze_width: float
    maze_height: float


def compute_maze_geometry(
    maze: Maze,
    page_width: float,
    page_height: float,
    region_x: float,
    region_y: float,
    region_w: float,
    region_h: float,
) -> MazeGeometry:
    rows = [r for r, _ in maze.active_cells]
    cols = [c for _, c in maze.active_cells]
    min_row, max_row = min(rows), max(rows)
    min_col, max_col = min(cols), max(cols)

    span_rows = (max_row - min_row + 1)
    span_cols = (max_col - min_col + 1)

    available_width = min(region_w, page_width * 0.94)
    available_height = min(region_h, page_height * 0.82)
    cell_size = min(available_width / span_cols, available_height / span_rows)

    maze_width = span_cols * cell_size
    maze_height = span_rows * cell_size

    # True centering by bounding box math.
    offset_x = region_x + (region_w - maze_width) / 2
    offset_y = region_y + (region_h - maze_height) / 2

    return MazeGeometry(
        cell_size=cell_size,
        offset_x=offset_x,
        offset_y=offset_y,
        min_row=min_row,
        min_col=min_col,
        max_row=max_row,
        max_col=max_col,
        maze_width=maze_width,
        maze_height=maze_height,
    )


def cell_box(cell: Cell, geom: MazeGeometry) -> tuple[float, float, float, float]:
    r, c = cell
    x0 = geom.offset_x + (c - geom.min_col) * geom.cell_size
    y0 = geom.offset_y + (geom.max_row - r) * geom.cell_size
    return x0, y0, x0 + geom.cell_size, y0 + geom.cell_size


def opening_point(cell: Cell, side: str, geom: MazeGeometry) -> tuple[float, float]:
    x0, y0, x1, y1 = cell_box(cell, geom)
    if side == "N":
        return (x0 + x1) / 2, y1
    if side == "S":
        return (x0 + x1) / 2, y0
    if side == "W":
        return x0, (y0 + y1) / 2
    return x1, (y0 + y1) / 2


def icon_center_from_opening(open_x: float, open_y: float, side: str, icon_size: float, factor: float) -> tuple[float, float]:
    dx, dy = {
        "N": (0.0, 1.0),
        "S": (0.0, -1.0),
        "W": (-1.0, 0.0),
        "E": (1.0, 0.0),
    }[side]
    return open_x + (dx * icon_size * factor), open_y + (dy * icon_size * factor)


def clamp_point(x: float, y: float, min_x: float, min_y: float, max_x: float, max_y: float) -> tuple[float, float]:
    return max(min_x, min(max_x, x)), max(min_y, min(max_y, y))
