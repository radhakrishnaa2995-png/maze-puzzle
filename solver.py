"""Maze solving helpers."""

from __future__ import annotations

from collections import deque
from typing import Dict, List, Tuple

from maze_generator import DIRS, Maze

Cell = Tuple[int, int]


def solve_maze(maze: Maze) -> List[Cell]:
    queue = deque([maze.start])
    parent: Dict[Cell, Cell | None] = {maze.start: None}

    while queue:
        cur = queue.popleft()
        if cur == maze.end:
            break

        r, c = cur
        for dname, (dr, dc) in DIRS.items():
            if maze.walls[cur][dname]:
                continue
            nxt = (r + dr, c + dc)
            if nxt in maze.active_cells and nxt not in parent:
                parent[nxt] = cur
                queue.append(nxt)

    if maze.end not in parent:
        return []

    path: List[Cell] = []
    cur: Cell | None = maze.end
    while cur is not None:
        path.append(cur)
        cur = parent[cur]
    path.reverse()
    return path
