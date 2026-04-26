"""Core maze generation using SVG-masked cell graphs."""

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


def _build_masked_cells(rows: int, cols: int, shape: str, shape_dir: str) -> Set[Cell]:
    mask = mask_for_shape(shape, shape_dir=shape_dir)
    cells: Set[Cell] = set()
    for r in range(rows):
        for c in range(cols):
            x, y = _cell_center(rows, cols, r, c)
            if mask(x, y):
                cells.add((r, c))

    if not cells:
        return cells

    # Keep only the largest connected component.
    unvisited = set(cells)
    components: list[Set[Cell]] = []
    while unvisited:
        seed = next(iter(unvisited))
        stack = [seed]
        unvisited.remove(seed)
        comp = set()
        while stack:
            cur = stack.pop()
            comp.add(cur)
            rr, cc = cur
            for dr, dc in DIRS.values():
                nxt = (rr + dr, cc + dc)
                if nxt in unvisited:
                    unvisited.remove(nxt)
                    stack.append(nxt)
        components.append(comp)

    components.sort(key=len, reverse=True)
    return components[0]


def _exposed_sides(cell: Cell, active_cells: Set[Cell]) -> list[str]:
    r, c = cell
    sides: list[str] = []
    for side, (dr, dc) in DIRS.items():
        if (r + dr, c + dc) not in active_cells:
            sides.append(side)
    return sides


def _pick_endpoint(active_cells: Set[Cell], prefer: str, rng: random.Random) -> tuple[Cell, str]:
    candidates: list[tuple[int, int, Cell, str]] = []
    for cell in active_cells:
        sides = _exposed_sides(cell, active_cells)
        if not sides:
            continue
        r, c = cell
        for side in sides:
            horiz = c if prefer == "left" else -c
            side_bonus = -1000 if (prefer == "left" and side == "W") or (prefer == "right" and side == "E") else 0
            candidates.append((horiz + side_bonus, abs(r), cell, side))

    if not candidates:
        fallback = rng.choice(list(active_cells))
        return fallback, "W" if prefer == "left" else "E"

    candidates.sort(key=lambda t: (t[0], t[1]))
    shortlist = candidates[: max(10, len(candidates) // 8)]
    _, _, chosen, side = rng.choice(shortlist)
    return chosen, side


def generate_maze(
    rows: int,
    cols: int,
    shape: str,
    difficulty_factor: float,
    rng: random.Random,
    shape_dir: str = "assets/shapes",
) -> Maze:
    active_cells = _build_masked_cells(rows, cols, shape, shape_dir)
    if len(active_cells) < 32:
        raise ValueError(f"Shape {shape} produced too few active cells.")

    walls: Dict[Cell, Dict[str, bool]] = {
        cell: {"N": True, "S": True, "W": True, "E": True} for cell in active_cells
    }

    start, start_open = _pick_endpoint(active_cells, prefer="left", rng=rng)
    end, end_open = _pick_endpoint(active_cells - {start}, prefer="right", rng=rng)

    visited: Set[Cell] = {start}
    stack: List[Cell] = [start]

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
            if len(stack) > 1 and rng.random() < (0.62 - (difficulty_factor * 0.34)):
                prev = stack[-2]
                cur_dir = (r - prev[0], c - prev[1])
                for idx, (_, nxt) in enumerate(neighbors):
                    nd = (nxt[0] - r, nxt[1] - c)
                    if nd == cur_dir:
                        neighbors.insert(0, neighbors.pop(idx))
                        break

            direction, nxt = neighbors[0]
            walls[cur][direction] = False
            walls[nxt][OPPOSITE[direction]] = False
            visited.add(nxt)
            stack.append(nxt)
        else:
            stack.pop()

    walls[start][start_open] = False
    walls[end][end_open] = False

    return Maze(
        rows=rows,
        cols=cols,
        shape=shape,
        active_cells=active_cells,
        walls=walls,
        start=start,
        end=end,
        start_open_side=start_open,
        end_open_side=end_open,
        difficulty="",
    )
