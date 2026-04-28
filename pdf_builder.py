# pdf_builder.py
"""Publication-ready scene maze puzzle book PDF builder."""

from __future__ import annotations

import math
import random
from dataclasses import dataclass
from hashlib import sha1
from io import BytesIO
from typing import Dict, List, Any

import numpy as np
from PIL import Image
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas

from icons import IconPair, load_icon_pairs
from maze_generator import Maze, generate_maze, maze_signature
from renderer import compute_maze_geometry, opening_point, cell_box, icon_center_from_opening
from solver import solve_maze

PAGE_W, PAGE_H = A4

PAD_X = 0.06
PAD_Y = 0.08
HEADER_H_PX = 110.0
BOTTOM_MARGIN_PX = 50.0
MAZE_TARGET_W_RATIO = 0.75
MAZE_TARGET_H_RATIO = 0.68

PASTEL_PALETTE = [
    colors.HexColor("#DBEAFE"),
    colors.HexColor("#FBCFE8"),
    colors.HexColor("#FED7AA"),
    colors.HexColor("#D1FAE5"),
    colors.HexColor("#E9D5FF"),
    colors.HexColor("#FEF3C7"),
]
ACCENTS = [
    colors.HexColor("#2563EB"),
    colors.HexColor("#DB2777"),
    colors.HexColor("#EA580C"),
    colors.HexColor("#059669"),
    colors.HexColor("#7C3AED"),
    colors.HexColor("#CA8A04"),
]

STORIES: Dict[str, str] = {
    "car": "Help the car reach the garage before it runs out of fuel!",
    "cat": "Can the cat find its milk bowl?",
    "rocket": "Help the rocket reach the planet safely!",
    "pirate": "Guide the pirate ship to the treasure chest!",
    "train": "Help the train reach the station on time!",
}

DEFAULT_DIFFICULTY_PROFILES: dict[str, dict[str, Any]] = {
    "easy": {"rows_range": [14, 18], "cols_range": [14, 18]},
    "medium": {"rows_range": [18, 24], "cols_range": [20, 28]},
    "hard": {"rows_range": [24, 32], "cols_range": [28, 38]},
}


@dataclass
class PuzzlePage:
    puzzle_number: int
    pair: IconPair
    maze: Maze
    solution: list[tuple[int, int]]
    difficulty: str


@dataclass(frozen=True)
class Layout:
    left: float
    right: float
    bottom: float
    top: float
    header_y: float
    story_y: float
    maze_top: float
    maze_bottom: float
    maze_region_x: float
    maze_region_y: float
    maze_region_w: float
    maze_region_h: float


@dataclass(frozen=True)
class IconPlacement:
    start_left: float
    start_bottom: float
    end_left: float
    end_bottom: float
    size: float
    valid: bool


def _difficulty_for_page(page_idx: int, total_pages: int, profiles: dict[str, Any] | None = None) -> tuple[str, int, int, float]:
    profiles = profiles or {}
    progress = (page_idx + 1) / max(1, total_pages)
    if progress <= 0.30:
        pr = profiles.get("easy", {})
        rr = pr.get("rows_range", [14, 18])
        cr = pr.get("cols_range", [14, 18])
        return "Easy", int(rr[0]), int(cr[0]), 0.18
    if progress <= 0.70:
        pr = profiles.get("medium", {})
        rr = pr.get("rows_range", [18, 24])
        cr = pr.get("cols_range", [20, 28])
        return "Medium", int((rr[0] + rr[1]) / 2), int((cr[0] + cr[1]) / 2), 0.56
    pr = profiles.get("hard", {})
    rr = pr.get("rows_range", [24, 32])
    cr = pr.get("cols_range", [28, 38])
    return "Hard", int(rr[1]), int(cr[1]), 0.92


def _difficulty_stars_count(name: str) -> int:
    return {"Easy": 1, "Medium": 2, "Hard": 3}.get(name, 1)


def _layout() -> Layout:
    left = PAGE_W * PAD_X
    right = PAGE_W * (1 - PAD_X)
    bottom = PAGE_H * PAD_Y
    top = PAGE_H * (1 - PAD_Y)

    title_h = min(110.0, max(90.0, HEADER_H_PX))
    header_y = PAGE_H - title_h
    story_y = header_y - 28.0
    maze_top = PAGE_H - title_h
    maze_bottom = max(BOTTOM_MARGIN_PX, bottom)

    maze_region_w = PAGE_W * MAZE_TARGET_W_RATIO
    maze_region_h = min(PAGE_H * MAZE_TARGET_H_RATIO, maze_top - maze_bottom - 6.0)
    maze_region_x = (PAGE_W - maze_region_w) / 2
    maze_region_y = maze_bottom + ((maze_top - maze_bottom - maze_region_h) / 2)

    return Layout(
        left=left,
        right=right,
        bottom=bottom,
        top=top,
        header_y=header_y,
        story_y=story_y,
        maze_top=maze_top,
        maze_bottom=maze_bottom,
        maze_region_x=maze_region_x,
        maze_region_y=maze_region_y,
        maze_region_w=maze_region_w,
        maze_region_h=maze_region_h,
    )


def _palette_cycle(total: int, rng: random.Random) -> list[colors.Color]:
    base = PASTEL_PALETTE.copy()
    out: list[colors.Color] = []
    while len(out) < total:
        rng.shuffle(base)
        out.extend(base)
    return out[:total]


def _icon_plan(pages: int, pairs: list[IconPair], seed: int) -> list[IconPair]:
    rng = random.Random(seed ^ 0xC0FFEE)
    out: list[IconPair] = []
    while len(out) < pages:
        cycle = pairs.copy()
        rng.shuffle(cycle)
        out.extend(cycle)
    return out[:pages]


def _draw_page_frame(c: canvas.Canvas, bg: colors.Color, layout: Layout) -> None:
    c.setFillColor(bg)
    c.rect(0, 0, PAGE_W, PAGE_H, fill=1, stroke=0)
    # Intentionally no page border for a clean full-bleed worksheet look.


def _draw_bottom_page_no(c: canvas.Canvas, page_no: int) -> None:
    c.setFillColor(colors.HexColor("#334155"))
    c.setFont("Helvetica-Bold", 10)
    c.drawCentredString(PAGE_W / 2, PAGE_H * 0.03, f"Page {page_no}")


def _draw_star(c: canvas.Canvas, cx: float, cy: float, radius: float) -> None:
    pts = []
    for i in range(10):
        angle = (math.pi / 2) + (i * math.pi / 5)
        r = radius if i % 2 == 0 else radius * 0.45
        pts.append((cx + math.cos(angle) * r, cy + math.sin(angle) * r))
    p = c.beginPath()
    p.moveTo(*pts[0])
    for x, y in pts[1:]:
        p.lineTo(x, y)
    p.close()
    c.setFillColor(colors.HexColor("#FFD700"))
    c.setStrokeColor(colors.HexColor("#D4A017"))
    c.setLineWidth(0.7)
    c.drawPath(p, fill=1, stroke=1)


def _draw_cover(c: canvas.Canvas, bg: colors.Color, layout: Layout) -> None:
    _draw_page_frame(c, bg, layout)
    c.setFillColor(colors.HexColor("#0F172A"))
    c.setFont("Helvetica-Bold", 34)
    c.drawCentredString(PAGE_W / 2, PAGE_H * 0.66, "Fun Maze Puzzle Book for Kids")
    c.setFont("Helvetica-Bold", 18)
    c.setFillColor(colors.HexColor("#475569"))
    c.drawCentredString(PAGE_W / 2, PAGE_H * 0.58, "Easy • Medium • Hard")
    c.drawCentredString(PAGE_W / 2, PAGE_H * 0.53, "Ages 4–8")


def _draw_instructions(c: canvas.Canvas, bg: colors.Color, layout: Layout) -> None:
    _draw_page_frame(c, bg, layout)
    c.setFillColor(colors.HexColor("#0F172A"))
    c.setFont("Helvetica-Bold", 28)
    c.drawString(layout.left + 22, PAGE_H * 0.75, "How to Play")
    c.setFont("Helvetica", 15)
    lines = [
        "• Start from the first picture",
        "• Find your way through the maze",
        "• Reach the final object",
        "• Have fun!",
    ]
    y = PAGE_H * 0.66
    for line in lines:
        c.drawString(layout.left + 30, y, line)
        y -= 34


def _title_and_story(c: canvas.Canvas, accent: colors.Color, puzzle_no: int, difficulty: str, pair: IconPair, layout: Layout) -> None:
    title_h = 42.0
    c.setFillColor(accent)
    c.roundRect(layout.left, layout.header_y + 56.0, layout.right - layout.left, title_h, 12, fill=1, stroke=0)

    line_text = f"Puzzle {puzzle_no} • {difficulty}"
    c.setFillColor(colors.white)
    c.setFont("Helvetica-Bold", 16)
    c.drawString(layout.left + 16, layout.header_y + 56.0 + (title_h * 0.54), line_text)

    star_count = _difficulty_stars_count(difficulty)
    star_base_x = layout.left + 16 + (len(line_text) * 7.2) + 12
    star_y = layout.header_y + 56.0 + (title_h * 0.55)
    for i in range(star_count):
        _draw_star(c, star_base_x + (i * 17), star_y + 3, 5.5)

    c.setFillColor(colors.HexColor("#0F172A"))
    c.setFont("Helvetica-Bold", 20)
    c.drawString(layout.left, layout.story_y + 18, pair.title)

    c.setFont("Helvetica-Bold", 13)
    story = STORIES.get(pair.key, "Can you solve this maze?")
    c.drawString(layout.left, layout.story_y, story.upper())


def _fit_image_box(img_reader: ImageReader, max_w: float, max_h: float) -> tuple[float, float]:
    iw, ih = img_reader.getSize()
    if iw <= 0 or ih <= 0:
        return max_w, max_h
    scale = min(max_w / iw, max_h / ih)
    return iw * scale, ih * scale


def _prepare_icon_reader(path: str) -> ImageReader:
    img = Image.open(path).convert("RGBA")
    arr = np.array(img, dtype=np.uint8)
    rgb = arr[:, :, :3].astype(np.int16)
    alpha = arr[:, :, 3].astype(np.uint8)

    near_white = (rgb[:, :, 0] >= 242) & (rgb[:, :, 1] >= 242) & (rgb[:, :, 2] >= 242)
    alpha[near_white] = 0
    edge = (rgb[:, :, 0] >= 228) & (rgb[:, :, 1] >= 228) & (rgb[:, :, 2] >= 228) & (~near_white)
    alpha[edge] = np.minimum(alpha[edge], 120)

    arr[:, :, 3] = alpha
    cleaned = Image.fromarray(arr, mode="RGBA")
    buf = BytesIO()
    cleaned.save(buf, format="PNG")
    buf.seek(0)
    return ImageReader(buf)


def _draw_icon(c: canvas.Canvas, path: str, cx: float, cy: float, max_w: float, max_h: float) -> None:
    try:
        img = _prepare_icon_reader(path)
        w, h = _fit_image_box(img, max_w, max_h)
        c.drawImage(img, cx - (w / 2), cy - (h / 2), width=w, height=h, preserveAspectRatio=True, mask="auto")
    except Exception:
        c.setFillColor(colors.HexColor("#CBD5E1"))
        c.roundRect(cx - (max_w / 2), cy - (max_h / 2), max_w, max_h, 10, fill=1, stroke=0)


def _resolve_icon_placement(maze: Maze, layout: Layout, geom, icon_scale: float) -> IconPlacement:
    entry_row, entry_col, entry_side = maze.entry_opening
    exit_row, exit_col, exit_side = maze.exit_opening
    start_open_x, start_open_y = opening_point((entry_row, entry_col), entry_side, geom)
    end_open_x, end_open_y = opening_point((exit_row, exit_col), exit_side, geom)

    margin = 10.0
    gap = 5.0
    # Keep all icons strictly below story text to avoid overlap.
    max_icon_top = min(layout.story_y - 6.0, PAGE_H - margin)
    min_icon_bottom = margin
    min_x = margin
    max_x = PAGE_W - margin

    # Slightly larger fixed target while staying page-safe.
    base_icon_size = max(geom.cell_size * 3.45, PAGE_W * 0.105, geom.maze_height * icon_scale)

    def aligned_box_for_size(open_x: float, open_y: float, side: str, size: float) -> tuple[float, float, bool]:
        factor = 0.5 + (gap / size)
        cx, cy = icon_center_from_opening(open_x, open_y, side, size, factor=factor)
        left = cx - (size / 2)
        bottom = cy - (size / 2)
        right = left + size
        top = bottom + size
        fits = left >= min_x and right <= max_x and bottom >= min_icon_bottom and top <= max_icon_top
        return left, bottom, fits

    shared_size = base_icon_size
    for _ in range(28):
        s_left, s_bottom, s_fit = aligned_box_for_size(start_open_x, start_open_y, entry_side, shared_size)
        e_left, e_bottom, e_fit = aligned_box_for_size(end_open_x, end_open_y, exit_side, shared_size)
        if s_fit and e_fit:
            break
        shared_size *= 0.92
        if shared_size <= PAGE_W * 0.06:
            break

    s_left, s_bottom, _ = aligned_box_for_size(start_open_x, start_open_y, entry_side, shared_size)
    e_left, e_bottom, _ = aligned_box_for_size(end_open_x, end_open_y, exit_side, shared_size)
    s_left = max(min_x, min(max_x - shared_size, s_left))
    e_left = max(min_x, min(max_x - shared_size, e_left))
    s_bottom = max(min_icon_bottom, min(max_icon_top - shared_size, s_bottom))
    e_bottom = max(min_icon_bottom, min(max_icon_top - shared_size, e_bottom))

    # Disallow icon overlap; both icons must exist distinctly.
    overlap = not (
        (s_left + shared_size + 2.0) <= e_left
        or (e_left + shared_size + 2.0) <= s_left
        or (s_bottom + shared_size + 2.0) <= e_bottom
        or (e_bottom + shared_size + 2.0) <= s_bottom
    )
    valid = (not overlap) and (entry_side != exit_side)
    return IconPlacement(s_left, s_bottom, e_left, e_bottom, shared_size, valid)


def _draw_maze(
    c: canvas.Canvas,
    maze: Maze,
    layout: Layout,
    show_solution: bool,
    path: list[tuple[int, int]] | None,
    pair: IconPair,
    icon_scale: float,
) -> None:
    geom = compute_maze_geometry(
        maze,
        page_width=PAGE_W,
        page_height=PAGE_H,
        region_x=layout.maze_region_x,
        region_y=layout.maze_region_y,
        region_w=layout.maze_region_w,
        region_h=layout.maze_region_h,
    )

    # Validation checks for geometry-driven alignment.
    center_x = geom.offset_x + (geom.maze_width / 2)
    center_y = geom.offset_y + (geom.maze_height / 2)
    if abs(center_x - (PAGE_W / 2)) > PAGE_W * 0.06 or abs(center_y - (PAGE_H / 2)) > PAGE_H * 0.10:
        print("Warning: maze center drift detected; auto-centering has been applied.")

    maze_line_width = min(1.8, max(1.2, geom.cell_size * 0.10))
    outer_line_width = min(3.0, max(2.5, geom.cell_size * 0.20))

    c.setStrokeColor(colors.HexColor("#1F2937"))
    c.setLineWidth(maze_line_width)
    for rc in maze.active_cells:
        x0, y0, x1, y1 = cell_box(rc, geom)
        w = maze.walls[rc]
        if w["N"]:
            c.line(x0, y1, x1, y1)
        if w["S"]:
            c.line(x0, y0, x1, y0)
        if w["W"]:
            c.line(x0, y0, x0, y1)
        if w["E"]:
            c.line(x1, y0, x1, y1)

    c.setStrokeColor(colors.black)
    c.setLineWidth(outer_line_width)
    for rc in maze.active_cells:
        r, cc = rc
        x0, y0, x1, y1 = cell_box(rc, geom)
        for side, (dr, dc), seg in [
            ("N", (-1, 0), (x0, y1, x1, y1)),
            ("S", (1, 0), (x0, y0, x1, y0)),
            ("W", (0, -1), (x0, y0, x0, y1)),
            ("E", (0, 1), (x1, y0, x1, y1)),
        ]:
            nb = (r + dr, cc + dc)
            if nb in maze.active_cells:
                continue
            if rc == maze.start and side == maze.start_open_side:
                continue
            if rc == maze.end and side == maze.end_open_side:
                continue
            c.line(*seg)

    icon_place = _resolve_icon_placement(maze, layout, geom, icon_scale)
    start_left, start_bottom = icon_place.start_left, icon_place.start_bottom
    end_left, end_bottom = icon_place.end_left, icon_place.end_bottom
    shared_size = icon_place.size

    # Final validation guards.
    if geom.offset_y + geom.maze_height > layout.maze_top or geom.offset_y < layout.maze_bottom:
        raise ValueError("Maze geometry escaped reserved vertical zone.")
    if not icon_place.valid:
        raise ValueError("Icon placement invalid (overlap or side conflict).")

    _draw_icon(
        c,
        str(pair.start_path),
        start_left + (shared_size / 2),
        start_bottom + (shared_size / 2),
        shared_size,
        shared_size,
    )
    _draw_icon(
        c,
        str(pair.finish_path),
        end_left + (shared_size / 2),
        end_bottom + (shared_size / 2),
        shared_size,
        shared_size,
    )

    if show_solution and path:
        c.setStrokeColor(colors.HexColor("#DC2626"))
        c.setLineWidth(max(2.0, geom.cell_size * 0.20))
        pts = []
        for r, cc in path:
            if (r, cc) not in maze.active_cells:
                continue
            x0, y0, _, _ = cell_box((r, cc), geom)
            pts.append((x0 + geom.cell_size / 2, y0 + geom.cell_size / 2))
        for i in range(len(pts) - 1):
            c.line(*pts[i], *pts[i + 1])


def _unique_rng(seed: int, page: int, theme_key: str, difficulty: str, attempt: int) -> random.Random:
    h = sha1(f"{seed}|{page}|{theme_key}|{difficulty}|{attempt}".encode("utf-8")).hexdigest()
    return random.Random(int(h[:16], 16))


def build_book(
    output_file: str,
    pages: int,
    seed: int,
    title: str,
    icon_dir: str = "assets/icons",
    difficulty_profiles: dict[str, Any] | None = None,
    shape_dir: str | None = None,
    icon_scale: float = 0.2,
    anchor_cycle: list[list[str]] | None = None,
) -> None:
    # Backward compatibility for older call sites that still pass shape_dir.
    if shape_dir:
        icon_dir = shape_dir

    if difficulty_profiles is None:
        difficulty_profiles = DEFAULT_DIFFICULTY_PROFILES
    if anchor_cycle is None:
        anchor_cycle = [["tl", "br"], ["tr", "bl"], ["left", "right"], ["top", "bottom"]]

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
            custom_pair = anchor_cycle[idx % len(anchor_cycle)]
            start_anchor, end_anchor = custom_pair[0], custom_pair[1]
            candidate = generate_maze(rows, cols, pair.key, diff_factor, prng, start_anchor=start_anchor, end_anchor=end_anchor)
            candidate.difficulty = diff_name
            candidate_path = solve_maze(candidate)
            if not candidate_path:
                continue
            candidate_geom = compute_maze_geometry(
                candidate,
                page_width=PAGE_W,
                page_height=PAGE_H,
                region_x=layout.maze_region_x,
                region_y=layout.maze_region_y,
                region_w=layout.maze_region_w,
                region_h=layout.maze_region_h,
            )
            if not _resolve_icon_placement(candidate, layout, candidate_geom, icon_scale).valid:
                continue
            sig = maze_signature(candidate)
            if sig in seen_signatures:
                continue
            maze = candidate
            solution = candidate_path
            break

        if maze is None:
            prng = _unique_rng(seed, page_no, pair.key, diff_name, 999)
            custom_pair = anchor_cycle[idx % len(anchor_cycle)]
            start_anchor, end_anchor = custom_pair[0], custom_pair[1]
            maze = generate_maze(rows, cols, pair.key, diff_factor, prng, start_anchor=start_anchor, end_anchor=end_anchor)
            maze.difficulty = diff_name
            solution = solve_maze(maze)
            sig = maze_signature(maze)

        seen_signatures.add(sig)
        puzzles.append(PuzzlePage(idx + 1, pair, maze, solution, diff_name))

        _draw_page_frame(c, bg_order[page_no - 1], layout)
        _title_and_story(c, ACCENTS[idx % len(ACCENTS)], idx + 1, diff_name, pair, layout)
        _draw_maze(c, maze, layout, show_solution=False, path=None, pair=pair, icon_scale=icon_scale)
        _draw_bottom_page_no(c, page_no)
        c.showPage()

    solution_title_page = pages + 3
    _draw_page_frame(c, bg_order[solution_title_page - 1], layout)
    c.setFillColor(colors.HexColor("#0F172A"))
    c.setFont("Helvetica-Bold", 32)
    c.drawCentredString(PAGE_W / 2, PAGE_H * 0.60, "Solutions")
    _draw_bottom_page_no(c, solution_title_page)
    c.showPage()

    for i, puzzle in enumerate(puzzles, start=1):
        page_no = solution_title_page + i
        _draw_page_frame(c, bg_order[(solution_title_page + i - 1) % len(bg_order)], layout)
        _title_and_story(c, ACCENTS[(i - 1) % len(ACCENTS)], puzzle.puzzle_number, puzzle.difficulty, puzzle.pair, layout)
        _draw_maze(c, puzzle.maze, layout, show_solution=True, path=puzzle.solution, pair=puzzle.pair, icon_scale=icon_scale)
        _draw_bottom_page_no(c, page_no)
        c.showPage()

    final_page_no = solution_title_page + len(puzzles) + 1
    _draw_page_frame(c, bg_order[(final_page_no - 1) % len(bg_order)], layout)
    c.setFillColor(colors.HexColor("#0F172A"))
    c.setFont("Helvetica-Bold", 30)
    c.drawCentredString(PAGE_W / 2, PAGE_H * 0.62, "You Did Amazing!")
    c.setFont("Helvetica", 14)
    c.drawCentredString(PAGE_W / 2, PAGE_H * 0.54, "Great job solving the mazes!")
    c.drawString(layout.left + 24, PAGE_H * 0.38, "Name: ______________________________")
    _draw_bottom_page_no(c, final_page_no)
    c.showPage()

    c.save()
