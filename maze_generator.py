"""Core maze generation using masked cell graphs."""

from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Dict, List, Set, Tuple

from shapes import mask_for_shape

Cell = Tuple[int, int]


@dataclass
class Maze:
    rows: int
    cols: int
    shape: str
    active_cells: Set[Cell]
    walls: Dict[Cell, Dict[str, bool]]
    start: Cell
    end: Cell
    start_open_side: str
    end_open_side: str
    difficulty: str


DIRS = {
    "N": (-1, 0),
    "S": (1, 0),
    "W": (0, -1),
    "E": (0, 1),
}
OPPOSITE = {"N": "S", "S": "N", "W": "E", "E": "W"}


def _cell_center(rows: int, cols: int, r: int, c: int) -> tuple[float, float]:
    x = ((c + 0.5) / cols) * 2 - 1
    y = ((r + 0.5) / rows) * 2 - 1
    return x, y


def _connected_component(cells: Set[Cell]) -> Set[Cell]:
    if not cells:
        return set()
    start = next(iter(cells))
    stack = [start]
    seen = {start}
    while stack:
        r, c = stack.pop()
        for dr, dc in DIRS.values():
            nxt = (r + dr, c + dc)
            if nxt in cells and nxt not in seen:
                seen.add(nxt)
                stack.append(nxt)
    return seen


def _build_masked_cells(rows: int, cols: int, shape: str) -> Set[Cell]:
    mask = mask_for_shape(shape)
    cells: Set[Cell] = set()
    for r in range(rows):
        for c in range(cols):
            x, y = _cell_center(rows, cols, r, c)
            if mask(x, y):
                cells.add((r, c))

    if not cells:
        return cells
    largest = _connected_component(cells)
    if len(largest) < len(cells):
        cells = largest
    return cells


def _exposed_sides(cell: Cell, active_cells: Set[Cell]) -> list[str]:
    r, c = cell
    sides: list[str] = []
    for side, (dr, dc) in DIRS.items():
        if (r + dr, c + dc) not in active_cells:
            sides.append(side)
    return sides


def _side_priority(shape: str, side: str) -> int:
    # Prefer left opening for start, right opening for finish when possible.
    if shape in {"Circle", "Oval", "Heart", "Star", "Hexagon", "Diamond", "Square", "Rectangle", "Triangle", "Spiral"}:
        order = {"W": 0, "E": 1, "N": 2, "S": 3}
        return order.get(side, 99)
    return 99


def _pick_endpoint(active_cells: Set[Cell], prefer: str, shape: str, rng: random.Random) -> tuple[Cell, str]:
    candidates: list[tuple[int, int, Cell, str]] = []
    for cell in active_cells:
        sides = _exposed_sides(cell, active_cells)
        if not sides:
            continue
        for side in sides:
            r, c = cell
            horizontal_score = c if prefer == "left" else -c
            side_pref = 0
            if prefer == "left" and side == "W":
                side_pref = -1000
            if prefer == "right" and side == "E":
                side_pref = -1000
            candidates.append((horizontal_score + side_pref, _side_priority(shape, side), cell, side))

    if not candidates:
        # Fallback: any cell with any side
        cell = rng.choice(list(active_cells))
        return cell, "W" if prefer == "left" else "E"

    candidates.sort(key=lambda t: (t[0], t[1]))
    shortlist = candidates[: max(5, len(candidates) // 10)]
    _, _, cell, side = rng.choice(shortlist)
    return cell, side


def generate_maze(
    rows: int,
    cols: int,
    shape: str,
    difficulty_factor: float,
    rng: random.Random,
) -> Maze:
    """Generate a perfect maze constrained to a shape mask."""
    active_cells = _build_masked_cells(rows, cols, shape)
    if len(active_cells) < 10:
        raise ValueError(f"Shape {shape} produced too few cells.")

    walls: Dict[Cell, Dict[str, bool]] = {
        cell: {"N": True, "S": True, "W": True, "E": True} for cell in active_cells
    }

    start, start_open_side = _pick_endpoint(active_cells, prefer="left", shape=shape, rng=rng)
    end, end_open_side = _pick_endpoint(active_cells, prefer="right", shape=shape, rng=rng)
    if start == end:
        end, end_open_side = _pick_endpoint(active_cells - {start}, prefer="right", shape=shape, rng=rng)

    visited: Set[Cell] = set()
    stack: List[Cell] = [start]
    visited.add(start)

    while stack:
        cur = stack[-1]
        r, c = cur
        neighbors = []
        for dname, (dr, dc) in DIRS.items():
            nxt = (r + dr, c + dc)
            if nxt in active_cells and nxt not in visited:
                neighbors.append((dname, nxt))

        if neighbors:
            rng.shuffle(neighbors)
            if len(stack) > 1 and rng.random() < (0.65 - (difficulty_factor * 0.35)):
                prev = stack[-2]
                pd = (r - prev[0], c - prev[1])
                for idx, (_, nxt) in enumerate(neighbors):
                    nd = (nxt[0] - r, nxt[1] - c)
                    if nd == pd:
                        neighbors.insert(0, neighbors.pop(idx))
                        break

            direction, nxt = neighbors[0]
            walls[cur][direction] = False
            walls[nxt][OPPOSITE[direction]] = False
            visited.add(nxt)
            stack.append(nxt)
        else:
            stack.pop()

    # Open entrance/exit to the outside world.
    walls[start][start_open_side] = False
    walls[end][end_open_side] = False

    return Maze(
        rows=rows,
        cols=cols,
        shape=shape,
        active_cells=active_cells,
        walls=walls,
        start=start,
        end=end,
        start_open_side=start_open_side,
        end_open_side=end_open_side,
        difficulty="",
    )
