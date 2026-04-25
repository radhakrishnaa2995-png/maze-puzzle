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

    # Keep only largest connected component to avoid isolated islands.
    if not cells:
        return cells
    largest = _connected_component(cells)
    if len(largest) < len(cells):
        cells = largest
    return cells


def _pick_endpoints(active_cells: Set[Cell], cols: int, rng: random.Random) -> tuple[Cell, Cell]:
    leftish = sorted(active_cells, key=lambda cell: (cell[1], cell[0]))
    rightish = sorted(active_cells, key=lambda cell: (-cell[1], cell[0]))

    left_candidates = leftish[: max(3, len(leftish) // 15)]
    right_candidates = rightish[: max(3, len(rightish) // 15)]

    start = rng.choice(left_candidates)
    end = rng.choice(right_candidates)
    if start == end:
        end = rightish[0]
    return start, end


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

    start, end = _pick_endpoints(active_cells, cols, rng)

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

        # Difficulty by directional stability: easier => straighter corridors.
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

    return Maze(
        rows=rows,
        cols=cols,
        shape=shape,
        active_cells=active_cells,
        walls=walls,
        start=start,
        end=end,
        difficulty="",
    )
