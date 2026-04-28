from typing import Dict, List, Any

# ... keep existing imports and code above ...

STORIES: Dict[str, str] = {
    "car": "Help the car reach the garage before it runs out of fuel!",
    "cat": "Can the cat find its milk bowl?",
    "rocket": "Help the rocket reach the planet safely!",
    "pirate": "Guide the pirate ship to the treasure chest!",
    "train": "Help the train reach the station on time!",
}

DEFAULT_DIFFICULTY_PROFILES: dict[str, dict[str, Any]] = {
    "easy": {"rows_range": [14, 20], "cols_range": [18, 28]},
    "medium": {"rows_range": [20, 30], "cols_range": [24, 36]},
    "hard": {"rows_range": [26, 36], "cols_range": [32, 44]},
}

def _difficulty_for_page(page_idx: int, total_pages: int, profiles: dict[str, Any] | None = None) -> tuple[str, int, int, float]:
    profiles = profiles or {}
    progress = (page_idx + 1) / max(1, total_pages)
    if progress <= 0.30:
        pr = profiles.get("easy", {})
        rr = pr.get("rows_range", [14, 20])
        cr = pr.get("cols_range", [18, 28])
        return "Easy", int(rr[0]), int(cr[0]), 0.18
    if progress <= 0.70:
        pr = profiles.get("medium", {})
        rr = pr.get("rows_range", [20, 30])
        cr = pr.get("cols_range", [24, 36])
        return "Medium", int((rr[0] + rr[1]) / 2), int((cr[0] + cr[1]) / 2), 0.56
    pr = profiles.get("hard", {})
    rr = pr.get("rows_range", [26, 36])
    cr = pr.get("cols_range", [32, 44])
    return "Hard", int(rr[1]), int(cr[1]), 0.92

# ... keep existing code ...

def build_book(
    output_file: str,
    pages: int,
    seed: int,
    title: str,
    icon_dir: str = "assets/icons",
    difficulty_profiles: dict[str, Any] | None = None,
    shape_dir: str | None = None,
) -> None:
    # Backward compatibility for older call sites that still pass shape_dir.
    if shape_dir:
        icon_dir = shape_dir

    if difficulty_profiles is None:
        difficulty_profiles = DEFAULT_DIFFICULTY_PROFILES

    rng = random.Random(seed)
    c = canvas.Canvas(output_file, pagesize=A4)

    pairs = load_icon_pairs(icon_dir)
    plan = _icon_plan(pages, pairs, seed)
    bg_order = _palette_cycle((pages * 2) + 20, rng)
    layout = _layout()

    puzzles: List[PuzzlePage] = []
    seen_signatures: set[str] = set()

    _draw_cover(c, bg_order[0], layout)
    _draw_bottom_page_no(c, 1)
    c.showPage()

    _draw_instructions(c, bg_order[1], layout)
    _draw_bottom_page_no(c, 2)
    c.showPage()

    for idx in range(pages):
        page_no = idx + 3
        pair = plan[idx]
        diff_name, rows, cols, diff_factor = _difficulty_for_page(idx, pages, difficulty_profiles)

        maze = None
        solution: list[tuple[int, int]] = []
        sig = ""

        for attempt in range(36):
            prng = _unique_rng(seed, page_no, pair.key, diff_name, attempt)
            candidate = generate_maze(rows, cols, pair.key, diff_factor, prng, start_anchor="tl", end_anchor="br")
            candidate.difficulty = diff_name
            candidate_path = solve_maze(candidate)
            if not candidate_path:
                continue
            sig = maze_signature(candidate)
            if sig in seen_signatures:
                continue
            maze = candidate
            solution = candidate_path
            break

        if maze is None:
            prng = _unique_rng(seed, page_no, pair.key, diff_name, 999)
            maze = generate_maze(rows, cols, pair.key, diff_factor, prng, start_anchor="tl", end_anchor="br")
            maze.difficulty = diff_name
            solution = solve_maze(maze)
            sig = maze_signature(maze)

        seen_signatures.add(sig)
        puzzles.append(PuzzlePage(idx + 1, pair, maze, solution, diff_name))

        _draw_page_frame(c, bg_order[page_no - 1], layout)
        _title_and_story(c, ACCENTS[idx % len(ACCENTS)], idx + 1, diff_name, pair, layout)
        _draw_maze(c, maze, layout, show_solution=False, path=None, pair=pair)
        _draw_bottom_page_no(c, page_no)
        c.showPage()

    # ... keep remainder of function unchanged ...
