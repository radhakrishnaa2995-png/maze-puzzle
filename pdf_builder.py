# pdf_builder.py
"""Publication-ready scene maze puzzle book PDF builder."""

from __future__ import annotations

import random
from dataclasses import dataclass
from hashlib import sha1
from io import BytesIO
from typing import Dict, List

import numpy as np
from PIL import Image
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas

from icons import IconPair, load_icon_pairs
from maze_generator import Maze, generate_maze, maze_signature
from solver import solve_maze

PAGE_W, PAGE_H = A4

# Balanced page grid.
PAD_X = 0.09
PAD_Y = 0.08
HEADER_H = 0.10
STORY_H = 0.06
MAZE_W = 0.70
MAZE_H = 0.68

START_X = 0.10
START_Y = 0.74
FINISH_X = 0.80
FINISH_Y = 0.16

START_W = 0.20
START_H = 0.22
FINISH_W = 0.16
FINISH_H = 0.18

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
    maze_x: float
    maze_y: float
    maze_w: float
    maze_h: float
    start_cx: float
    start_cy: float
    finish_cx: float
    finish_cy: float


def _difficulty_for_page(page_idx: int, total_pages: int) -> tuple[str, int, int, float]:
    progress = (page_idx + 1) / max(1, total_pages)
    if progress <= 0.30:
        return "Easy", 22, 28, 0.18
    if progress <= 0.70:
        return "Medium", 30, 38, 0.56
    return "Hard", 38, 48, 0.92


def _difficulty_stars(name: str) -> str:
    return {"Easy": "⭐", "Medium": "⭐⭐", "Hard": "⭐⭐⭐"}.get(name, "")


def _layout() -> Layout:
    left = PAGE_W * PAD_X
    right = PAGE_W * (1 - PAD_X)
    bottom = PAGE_H * PAD_Y
    top = PAGE_H * (1 - PAD_Y)

    header_y = top - (PAGE_H * HEADER_H)
    story_y = header_y - (PAGE_H * STORY_H)

    maze_w = PAGE_W * MAZE_W
    maze_h = PAGE_H * MAZE_H
    maze_x = (PAGE_W - maze_w) / 2
    maze_y = (PAGE_H - maze_h) / 2 - (PAGE_H * 0.02)

    return Layout(
        left=left,
        right=right,
        bottom=bottom,
        top=top,
        header_y=header_y,
        story_y=story_y,
        maze_x=maze_x,
        maze_y=maze_y,
        maze_w=maze_w,
        maze_h=maze_h,
        start_cx=PAGE_W * START_X,
        start_cy=PAGE_H * START_Y,
        finish_cx=PAGE_W * FINISH_X,
        finish_cy=PAGE_H * FINISH_Y,
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
    c.setStrokeColor(colors.HexColor("#1E293B"))
    c.setLineWidth(1.2)
    c.roundRect(layout.left, layout.bottom, layout.right - layout.left, layout.top - layout.bottom, 12, fill=0, stroke=1)


def _draw_bottom_page_no(c: canvas.Canvas, page_no: int) -> None:
    c.setFillColor(colors.HexColor("#334155"))
    c.setFont("Helvetica-Bold", 10)
    c.drawCentredString(PAGE_W / 2, PAGE_H * 0.03, f"Page {page_no}")


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
    title_h = PAGE_H * 0.064
    c.setFillColor(accent)
    c.roundRect(layout.left, layout.header_y, layout.right - layout.left, title_h, 12, fill=1, stroke=0)

    c.setFillColor(colors.white)
    c.setFont("Helvetica-Bold", 16)
    c.drawString(layout.left + 16, layout.header_y + (title_h * 0.55), f"Puzzle {puzzle_no} • {difficulty} {_difficulty_stars(difficulty)}")

    c.setFillColor(colors.HexColor("#0F172A"))
    c.setFont("Helvetica-Bold", 25)
    c.drawString(layout.left, layout.story_y + 18, pair.title)

    c.setFont("Helvetica-Oblique", 12)
    story = STORIES.get(pair.key, "Can you solve this maze?")
    c.drawString(layout.left, layout.story_y - 2, f"\"{story}\"")


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


def _draw_maze(c: canvas.Canvas, maze: Maze, layout: Layout, show_solution: bool, path: list[tuple[int, int]] | None, pair: IconPair) -> None:
    rows, cols = maze.rows, maze.cols
    cell = min(layout.maze_w / cols, layout.maze_h / rows)
    ox = layout.maze_x + (layout.maze_w - cols * cell) / 2
    oy = layout.maze_y + (layout.maze_h - rows * cell) / 2

    def box(rc: tuple[int, int]) -> tuple[float, float, float, float]:
        r, cc = rc
        x0 = ox + (cc * cell)
        y0 = oy + ((rows - 1 - r) * cell)
        return x0, y0, x0 + cell, y0 + cell

    c.setStrokeColor(colors.HexColor("#1F2937"))
    c.setLineWidth(max(0.85, cell * 0.09))
    for rc in maze.active_cells:
        x0, y0, x1, y1 = box(rc)
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
    c.setLineWidth(max(1.8, cell * 0.16))
    for rc in maze.active_cells:
        r, cc = rc
        x0, y0, x1, y1 = box(rc)
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

    _draw_icon(c, str(pair.start_path), layout.start_cx, layout.start_cy, PAGE_W * START_W, PAGE_H * START_H)
    _draw_icon(c, str(pair.finish_path), layout.finish_cx, layout.finish_cy, PAGE_W * FINISH_W, PAGE_H * FINISH_H)

    if show_solution and path:
        c.setStrokeColor(colors.HexColor("#DC2626"))
        c.setLineWidth(max(1.8, cell * 0.18))
        pts = []
        for r, cc in path:
            if (r, cc) not in maze.active_cells:
                continue
            x0, y0, _, _ = box((r, cc))
            pts.append((x0 + cell / 2, y0 + cell / 2))
        for i in range(len(pts) - 1):
            c.line(*pts[i], *pts[i + 1])


def _unique_rng(seed: int, page: int, theme_key: str, difficulty: str, attempt: int) -> random.Random:
    h = sha1(f"{seed}|{page}|{theme_key}|{difficulty}|{attempt}".encode("utf-8")).hexdigest()
    return random.Random(int(h[:16], 16))


def build_book(output_file: str, pages: int, seed: int, title: str, icon_dir: str = "assets/icons") -> None:
    rng = random.Random(seed)
    c = canvas.Canvas(output_file, pagesize=A4)

    pairs = load_icon_pairs(icon_dir)
    plan = _icon_plan(pages, pairs, seed)
    bg_order = _palette_cycle((pages * 2) + 20, rng)
    layout = _layout()

    puzzles: List[PuzzlePage] = []
    seen_signatures: set[str] = set()

    # 1) Cover page
    _draw_cover(c, bg_order[0], layout)
    _draw_bottom_page_no(c, 1)
    c.showPage()

    # 2) How to play page
    _draw_instructions(c, bg_order[1], layout)
    _draw_bottom_page_no(c, 2)
    c.showPage()

    # 3) Puzzle pages
    for idx in range(pages):
        page_no = idx + 3
        pair = plan[idx]
        diff_name, rows, cols, diff_factor = _difficulty_for_page(idx, pages)

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

    # 4) Solutions title
    solution_title_page = pages + 3
    _draw_page_frame(c, bg_order[solution_title_page - 1], layout)
    c.setFillColor(colors.HexColor("#0F172A"))
    c.setFont("Helvetica-Bold", 32)
    c.drawCentredString(PAGE_W / 2, PAGE_H * 0.60, "Solutions")
    _draw_bottom_page_no(c, solution_title_page)
    c.showPage()

    # 4b) solution pages
    for i, puzzle in enumerate(puzzles, start=1):
        page_no = solution_title_page + i
        _draw_page_frame(c, bg_order[(solution_title_page + i - 1) % len(bg_order)], layout)
        _title_and_story(c, ACCENTS[(i - 1) % len(ACCENTS)], puzzle.puzzle_number, puzzle.difficulty, puzzle.pair, layout)
        _draw_maze(c, puzzle.maze, layout, show_solution=True, path=puzzle.solution, pair=puzzle.pair)
        _draw_bottom_page_no(c, page_no)
        c.showPage()

    # 5) Final page
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
