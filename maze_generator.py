"""Premium rectangular scene-maze generation utilities."""

from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Dict, List, Tuple

Cell = Tuple[int, int]


@dataclass
class Maze:
    rows: int
    cols: int
    theme: str
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


def _all_cells(rows: int, cols: int) -> List[Cell]:
    return [(r, c) for r in range(rows) for c in range(cols)]


def _opening_from_anchor(rows: int, cols: int, anchor: str, is_start: bool) -> tuple[Cell, str]:
    if anchor == "tl":
        return ((0, 0), "W" if is_start else "N")
    if anchor == "tr":
        return ((0, cols - 1), "N" if is_start else "E")
    if anchor == "bl":
        return ((rows - 1, 0), "W" if is_start else "S")
    if anchor == "br":
        return ((rows - 1, cols - 1), "E" if is_start else "S")
    if anchor == "left":
        return ((rows // 2, 0), "W")
    if anchor == "right":
        return ((rows // 2, cols - 1), "E")
    return ((0, 0), "W") if is_start else ((rows - 1, cols - 1), "E")


def _carve_dfs(
    rows: int,
    cols: int,
    walls: Dict[Cell, Dict[str, bool]],
    start: Cell,
    rng: random.Random,
    straight_preference: float,
) -> None:
    visited = {start}
    stack: list[Cell] = [start]
    prev_dir: dict[Cell, str] = {}

    while stack:
        r, c = stack[-1]
        options: list[tuple[str, Cell]] = []

        for side, (dr, dc) in DIRS.items():
            nr, nc = r + dr, c + dc
            nxt = (nr, nc)
            if 0 <= nr < rows and 0 <= nc < cols and nxt not in visited:
                options.append((side, nxt))

        if not options:
            stack.pop()
            continue

        if stack and rng.random() < straight_preference and stack[-1] in prev_dir:
            last_side = prev_dir[stack[-1]]
            straight = [opt for opt in options if opt[0] == last_side]
            side, nxt = rng.choice(straight or options)
        else:
            side, nxt = rng.choice(options)
        walls[(r, c)][side] = False
        walls[nxt][OPPOSITE[side]] = False
        prev_dir[nxt] = side
        visited.add(nxt)
        stack.append(nxt)


def _add_loops(rows: int, cols: int, walls: Dict[Cell, Dict[str, bool]], rng: random.Random, loop_factor: float) -> None:
    candidates: list[tuple[Cell, str, Cell]] = []

    for r in range(rows):
        for c in range(cols):
            cell = (r, c)
            for side, (dr, dc) in DIRS.items():
                nr, nc = r + dr, c + dc
                nxt = (nr, nc)
                if not (0 <= nr < rows and 0 <= nc < cols):
                    continue
                if walls[cell][side]:
                    rev = (nxt, OPPOSITE[side], cell)
                    if rev not in candidates:
                        candidates.append((cell, side, nxt))

    rng.shuffle(candidates)
    open_count = int(len(candidates) * loop_factor)
    for cell, side, nxt in candidates[:open_count]:
        walls[cell][side] = False
        walls[nxt][OPPOSITE[side]] = False


def maze_signature(maze: Maze) -> str:
    bits = []
    for cell in _all_cells(maze.rows, maze.cols):
        w = maze.walls[cell]
        bits.append(f"{cell[0]}:{cell[1]}:{int(w['N'])}{int(w['E'])}{int(w['S'])}{int(w['W'])}")
    return f"{maze.theme}|{maze.start}|{maze.end}|" + "|".join(bits)


def generate_maze(
    rows: int,
    cols: int,
    theme: str,
    difficulty_factor: float,
    rng: random.Random,
    start_anchor: str = "left",
    end_anchor: str = "right",
) -> Maze:
    rows = max(10, rows)
    cols = max(10, cols)

    cells = _all_cells(rows, cols)
    walls: Dict[Cell, Dict[str, bool]] = {cell: {"N": True, "S": True, "W": True, "E": True} for cell in cells}

    start, start_side = _opening_from_anchor(rows, cols, start_anchor, is_start=True)
    end, end_side = _opening_from_anchor(rows, cols, end_anchor, is_start=False)

    if start == end:
        end = (rows - 1, cols - 1)
        end_side = "E"

    # Difficulty profile (visibly different styles).
    if difficulty_factor <= 0.30:  # Easy
        straight_pref = 0.74
        loop_factor = 0.24
    elif difficulty_factor <= 0.75:  # Medium
        straight_pref = 0.48
        loop_factor = 0.12
    else:  # Hard
        straight_pref = 0.18
        loop_factor = 0.05

    _carve_dfs(rows, cols, walls, start, rng, straight_preference=straight_pref)
    _add_loops(rows, cols, walls, rng, loop_factor)

    walls[start][start_side] = False
    walls[end][end_side] = False

    return Maze(
        rows=rows,
        cols=cols,
        theme=theme,
        walls=walls,
        start=start,
        end=end,
        start_open_side=start_side,
        end_open_side=end_side,
        difficulty="",
    )
