def generate_maze(
    rows: int,
    cols: int,
    theme: str,
    difficulty_factor: float,
    rng: random.Random,
    start_anchor: str = "tl",
    end_anchor: str = "br",
) -> Maze:

    # =========================
    # DIFFICULTY SETTINGS
    # =========================
    if difficulty_factor <= 0.30:
        profile = "easy"
        rows = max(14, min(rows, 18))
        cols = max(14, min(cols, 20))
        straight_pref = 0.85
        loop_factor = 0.15

    elif difficulty_factor <= 0.75:
        profile = "medium"
        rows = max(18, min(rows, 26))
        cols = max(20, min(cols, 32))
        straight_pref = 0.55
        loop_factor = 0.10

    else:
        profile = "hard"
        rows = max(24, min(rows, 36))
        cols = max(28, min(cols, 42))
        straight_pref = 0.25
        loop_factor = 0.05

    # =========================
    # FULL GRID (NO CUT SHAPES)
    # =========================
    active = {(r, c) for r in range(rows) for c in range(cols)}

    walls: Dict[Cell, Dict[str, bool]] = {
        cell: {"N": True, "S": True, "W": True, "E": True}
        for cell in active
    }

    # =========================
    # ENTRY / EXIT FIX (IMPORTANT)
    # =========================
    def get_anchor(anchor):
        if anchor == "tl":
            return (0, 0), "W"
        elif anchor == "tr":
            return (0, cols - 1), "E"
        elif anchor == "bl":
            return (rows - 1, 0), "W"
        elif anchor == "br":
            return (rows - 1, cols - 1), "E"
        elif anchor == "top":
            return (0, cols // 2), "N"
        elif anchor == "bottom":
            return (rows - 1, cols // 2), "S"
        elif anchor == "left":
            return (rows // 2, 0), "W"
        elif anchor == "right":
            return (rows // 2, cols - 1), "E"
        else:
            return (0, 0), "W"

    start, start_side = get_anchor(start_anchor)
    end, end_side = get_anchor(end_anchor)

    # Ensure they are not same side
    if start == end:
        end = (rows - 1, cols - 1)

    # =========================
    # MAZE GENERATION (DFS BASE)
    # =========================
    visited = set([start])
    stack = [start]

    while stack:
        current = stack[-1]
        r, c = current

        neighbors = []
        for side, (dr, dc) in DIRS.items():
            nr, nc = r + dr, c + dc
            if (nr, nc) in active and (nr, nc) not in visited:
                neighbors.append((side, (nr, nc)))

        if not neighbors:
            stack.pop()
            continue

        if rng.random() < straight_pref:
            side, nxt = neighbors[0]
        else:
            side, nxt = rng.choice(neighbors)

        walls[current][side] = False
        walls[nxt][OPPOSITE[side]] = False

        visited.add(nxt)
        stack.append(nxt)

    # =========================
    # ADD LOOPS (VARIATION)
    # =========================
    all_edges = []
    for cell in active:
        for side, nxt in _neighbors(cell, rows, cols):
            if nxt in active and walls[cell][side]:
                all_edges.append((cell, side, nxt))

    rng.shuffle(all_edges)
    for cell, side, nxt in all_edges[: int(len(all_edges) * loop_factor)]:
        walls[cell][side] = False
        walls[nxt][OPPOSITE[side]] = False

    # =========================
    # FORCE CONNECT ENTRY → EXIT
    # =========================
    _force_connect(start, end, active, walls, rows, cols)

    # =========================
    # OPEN ENTRY & EXIT WALLS
    # =========================
    walls[start][start_side] = False
    walls[end][end_side] = False

    # =========================
    # FINAL RETURN
    # =========================
    return Maze(
        rows=rows,
        cols=cols,
        theme=theme,
        walls=walls,
        active_cells=active,
        start=start,
        end=end,
        start_open_side=start_side,
        end_open_side=end_side,
        entry_opening=(start[0], start[1], start_side),
        exit_opening=(end[0], end[1], end_side),
        difficulty=profile,
    )
