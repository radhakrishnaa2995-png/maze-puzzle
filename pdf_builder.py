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
MAZE_TARGET_W_RATIO = 0.66
MAZE_TARGET_H_RATIO = 0.62

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
    s = min(max_w / iw, max_h / ih)
    return iw * s, ih * s


def _prepare_icon_reader(path: str) -> ImageReader:
    with Image.open(path) as im:
        im = im.convert("RGBA")
        arr = np.asarray(im)
        alpha = arr[:, :, 3]
        if alpha.max() == 0:
            rgb = arr[:, :, :3].astype(np.int16)
            dist = np.sqrt(((rgb - 255) ** 2).sum(axis=2))
            alpha = np.where(dist < 14, 0, 255).astype(np.uint8)
            arr[:, :, 3] = alpha
        ys, xs = np.where(alpha > 0)
        if len(xs) > 0:
            crop = arr[ys.min() : ys.max() + 1, xs.min() : xs.max() + 1, :]
        else:
            crop = arr
        out = Image.fromarray(crop, mode="RGBA")
        bio = BytesIO()
        out.save(bio, format="PNG")
        bio.seek(0)
        return ImageReader(bio)


def _draw_icon(c: canvas.Canvas, path: str, cx: float, cy: float, max_w: float, max_h: float) -> None:
    img = _prepare_icon_reader(path)
    w, h = _fit_image_box(img, max_w, max_h)
    c.drawImage(
        img,
        cx - (w / 2),
        cy - (h / 2),
        width=w,
        height=h,
        mask="auto",
        preserveAspectRatio=True,
        anchor="c",
    )


def _resolve_icon_placement(maze: Maze, layout: Layout, geom, icon_scale: float) -> IconPlacement:
    icon_size = max(46.0, min(104.0, geom.cell_size * (2.2 + icon_scale * 1.8)))

    sx, sy = opening_point(maze.start, maze.start_open_side, geom)
    ex, ey = opening_point(maze.end, maze.end_open_side, geom)

    sx, sy = icon_center_from_opening(sx, sy, maze.start_open_side, icon_size, 0.64)
    ex, ey = icon_center_from_opening(ex, ey, maze.end_open_side, icon_size, 0.64)

    start_left = sx - (icon_size / 2)
    start_bottom = sy - (icon_size / 2)
    end_left = ex - (icon_size / 2)
    end_bottom = ey - (icon_size / 2)

    overlap = not (
        (start_left + icon_size) <= end_left
        or (end_left + icon_size) <= start_left
        or (start_bottom + icon_size) <= end_bottom
        or (end_bottom + icon_size) <= start_bottom
    )

    maze_left = geom.offset_x
    maze_right = geom.offset_x + geom.maze_width
    maze_bottom = geom.offset_y
    maze_top = geom.offset_y + geom.maze_height

    s_inside_maze = (
        (start_left < maze_right)
        and (start_left + icon_size > maze_left)
        and (start_bottom < maze_top)
        and (start_bottom + icon_size > maze_bottom)
    )
    e_inside_maze = (
        (end_left < maze_right)
        and (end_left + icon_size > maze_left)
        and (end_bottom < maze_top)
        and (end_bottom + icon_size > maze_bottom)
    )

    margin = 4.0
    in_bounds = all(
        [
            start_left >= layout.left - margin,
            start_bottom >= layout.bottom - margin,
            (start_left + icon_size) <= layout.right + margin,
            (start_bottom + icon_size) <= layout.top + margin,
            end_left >= layout.left - margin,
            end_bottom >= layout.bottom - margin,
            (end_left + icon_size) <= layout.right + margin,
            (end_bottom + icon_size) <= layout.top + margin,
        ]
    )

    return IconPlacement(
        start_left=start_left,
        start_bottom=start_bottom,
        end_left=end_left,
        end_bottom=end_bottom,
        size=icon_size,
        valid=(not overlap) and (not s_inside_maze) and (not e_inside_maze) and in_bounds,
    )


def _draw_maze(
    c: canvas.Canvas,
    maze: Maze,
    layout: Layout,
    show_solution: bool,
    path: list[tuple[int, int]] | None,
    pair: IconPair,
    icon_scale: float,
    bg_color: colors.Color,
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

    center_x = geom.offset_x + (geom.maze_width / 2)
    center_y = geom.offset_y + (geom.maze_height / 2)
    if abs(center_x - (PAGE_W / 2)) > PAGE_W * 0.06 or abs(center_y - (PAGE_H / 2)) > PAGE_H * 0.10:
        raise ValueError("Maze geometry failed centering constraints.")

    maze_line_width = min(1.8, max(1.2, geom.cell_size * 0.10))
    outer_line_width = min(3.0, max(2.5, geom.cell_size * 0.20))

    wall_color = colors.HexColor("#111827")
    c.setStrokeColor(wall_color)
    c.setLineWidth(maze_line_width)
    c.setLineCap(1)
    c.setLineJoin(1)
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

    outer_segments: list[tuple[float, float, float, float]] = []
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
            outer_segments.append(seg)

    icon_place = _resolve_icon_placement(maze, layout, geom, icon_scale)
    start_left, start_bottom = icon_place.start_left, icon_place.start_bottom
    end_left, end_bottom = icon_place.end_left, icon_place.end_bottom
    shared_size = icon_place.size

    if geom.offset_y + geom.maze_height > layout.maze_top or geom.offset_y < layout.maze_bottom:
        raise ValueError("Maze geometry escaped reserved vertical zone.")
    if not icon_place.valid:
        raise ValueError("Icon placement invalid (overlap or side conflict).")

    _draw_icon(c, str(pair.start_path), start_left + (shared_size / 2), start_bottom + (shared_size / 2), shared_size, shared_size)
    _draw_icon(c, str(pair.finish_path), end_left + (shared_size / 2), end_bottom + (shared_size / 2), shared_size, shared_size)

    c.setStrokeColor(bg_color)
    c.setLineWidth(max(outer_line_width * 6.0, shared_size * 0.20))
    for seg in outer_segments:
        c.line(*seg)

    c.setStrokeColor(wall_color)
    c.setLineWidth(outer_line_width)
    for seg in outer_segments:
        c.line(*seg)

    start_open_x, start_open_y = opening_point(maze.start, maze.start_open_side, geom)
    end_open_x, end_open_y = opening_point(maze.end, maze.end_open_side, geom)

    marker_r = max(6.0, geom.cell_size * 0.18)
    c.setFillColor(colors.HexColor("#16A34A"))
    c.setStrokeColor(colors.white)
    c.setLineWidth(1.2)
    c.circle(start_open_x, start_open_y, marker_r, stroke=1, fill=1)
    c.setFillColor(colors.HexColor("#B91C1C"))
    c.circle(end_open_x, end_open_y, marker_r, stroke=1, fill=1)

    c.setFillColor(colors.HexColor("#065F46"))
    c.setFont("Helvetica-Bold", 8)
    c.drawCentredString(start_open_x, start_open_y + marker_r + 3.5, "START")
    c.setFillColor(colors.HexColor("#7F1D1D"))
    c.drawCentredString(end_open_x, end_open_y + marker_r + 3.5, "FINISH")

    if show_solution and path:
        c.setStrokeColor(colors.HexColor("#DC2626"))
        c.setLineWidth(max(2.0, geom.cell_size * 0.20))
        pts = []
        for r, cc in path:
            if (r, cc) not in maze.active_cells:
                continue
            x0, y0, _, _ = cell_box((r, cc), geom)
            pts.append((x0 + (geom.cell_size / 2), y0 + (geom.cell_size / 2)))
        if len(pts) >= 2:
            p = c.beginPath()
            p.moveTo(*pts[0])
            for px, py in pts[1:]:
                p.lineTo(px, py)
            c.drawPath(p, stroke=1, fill=0)


def _unique_rng(seed: int, page_no: int, key: str, diff: str, attempt: int) -> random.Random:
    digest = sha1(f"{seed}|{page_no}|{key}|{diff}|{attempt}".encode("utf-8")).digest()
    return random.Random(int.from_bytes(digest[:8], "big"))


def _corner_bias_pair(idx: int, pair: IconPair) -> tuple[str, str]:
    cycle = [("tl", "br"), ("tr", "bl"), ("bl", "tr"), ("br", "tl")]
    return cycle[idx % len(cycle)]


def build_book(
    output_file: str,
    pages: int,
    seed: int,
    title: str,
    icon_dir: str,
    difficulty_profiles: dict[str, dict[str, Any]] | None = None,
    icon_scale: float = 0.20,
    anchor_cycle: list[list[str]] | None = None,
) -> None:
    rng = random.Random(seed)
    c = canvas.Canvas(output_file, pagesize=A4)
    layout = _layout()

    all_pairs = load_icon_pairs(icon_dir)
    pairs = _icon_plan(pages, all_pairs, seed)
    profiles = difficulty_profiles or DEFAULT_DIFFICULTY_PROFILES
    bg_order = _palette_cycle(pages + 8, rng)

    _draw_cover(c, bg_order[0], layout)
    _draw_bottom_page_no(c, 1)
    c.showPage()

    _draw_instructions(c, bg_order[1], layout)
    _draw_bottom_page_no(c, 2)
    c.showPage()

    puzzles: list[PuzzlePage] = []
    seen_signatures: set[str] = set()

    for idx, pair in enumerate(pairs):
        page_no = idx + 3
        diff_name, rows, cols, diff_factor = _difficulty_for_page(idx, pages, profiles)

        maze: Maze | None = None
        solution: list[tuple[int, int]] | None = None
        sig: str | None = None

        for attempt in range(40):
            prng = _unique_rng(seed, page_no, pair.key, diff_name, attempt)
            start_anchor, end_anchor = _corner_bias_pair(idx, pair)
            candidate = generate_maze(
                rows,
                cols,
                pair.key,
                diff_factor,
                prng,
                start_anchor=start_anchor,
                end_anchor=end_anchor,
            )
            candidate.difficulty = diff_name
            candidate_solution = solve_maze(candidate)
            if not candidate_solution:
                continue

            candidate_sig = maze_signature(candidate)
            if candidate_sig in seen_signatures:
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
            placement = _resolve_icon_placement(candidate, layout, candidate_geom, icon_scale)
            if not placement.valid:
                continue

            maze = candidate
            solution = candidate_solution
            sig = candidate_sig
            break

        if maze is None:
            rescue_profiles = [
                (max(12, rows - 2), max(12, cols - 2)),
                (max(10, rows - 4), max(10, cols - 4)),
                (rows, cols),
            ]
            for rescue_rows, rescue_cols in rescue_profiles:
                for backup_attempt in range(80):
                    prng = _unique_rng(seed, page_no, pair.key, diff_name, backup_attempt)
                    start_anchor, end_anchor = _corner_bias_pair(idx, pair)
                    candidate = generate_maze(
                        rescue_rows,
                        rescue_cols,
                        pair.key,
                        diff_factor,
                        prng,
                        start_anchor=start_anchor,
                        end_anchor=end_anchor,
                    )
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
                    maze = candidate
                    solution = candidate_path
                    sig = maze_signature(candidate)
                    break
                if maze is not None:
                    break
            if maze is None:
                raise RuntimeError(f"Unable to place non-overlapping large icons for page {page_no}.")

        seen_signatures.add(sig)
        puzzles.append(PuzzlePage(idx + 1, pair, maze, solution, diff_name))

        _draw_page_frame(c, bg_order[page_no - 1], layout)
        _title_and_story(c, ACCENTS[idx % len(ACCENTS)], idx + 1, diff_name, pair, layout)
        _draw_maze(c, maze, layout, show_solution=False, path=None, pair=pair, icon_scale=icon_scale, bg_color=bg_order[page_no - 1])
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
        _draw_maze(
            c,
            puzzle.maze,
            layout,
            show_solution=True,
            path=puzzle.solution,
            pair=puzzle.pair,
            icon_scale=icon_scale,
            bg_color=bg_order[(solution_title_page + i - 1) % len(bg_order)],
        )
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
