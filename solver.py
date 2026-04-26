# solver.py
"""Maze solver utilities."""

from __future__ import annotations

from collections import deque
from typing import Dict, List, Tuple

from maze_generator import DIRS, Maze

Cell = Tuple[int, int]


def solve_maze(maze: Maze) -> List[Cell]:
    q = deque([maze.start])
    parent: Dict[Cell, Cell | None] = {maze.start: None}

    while q:
        cur = q.popleft()
        if cur == maze.end:
            break

        r, c = cur
        for side, (dr, dc) in DIRS.items():
            if maze.walls[cur][side]:
                continue
            nxt = (r + dr, c + dc)
            if nxt in maze.active_cells and nxt not in parent:
                parent[nxt] = cur
                q.append(nxt)

    if maze.end not in parent:
        return []

    path: List[Cell] = []
    node: Cell | None = maze.end
    while node is not None:
        path.append(node)
        node = parent[node]
    path.reverse()
    return path
