# pdf_builder.py
"""Premium scene maze puzzle book PDF builder with fixed worksheet-style zones."""

from __future__ import annotations

import random
from io import BytesIO
from dataclasses import dataclass
from hashlib import sha1
from typing import List

import numpy as np
from PIL import Image
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import inch
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas

from icons import IconPair, load_icon_pairs
from maze_generator import Maze, generate_maze, maze_signature
from solver import solve_maze

PAGE_W, PAGE_H = A4

SAFE_LEFT = 0.45 * inch
SAFE_RIGHT = 0.45 * inch
SAFE_TOP = 0.45 * inch
SAFE_BOTTOM = 0.45 * inch

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


@dataclass
class PuzzlePage:
    puzzle_number: int
    pair: IconPair
    maze: Maze
    solution: list[tuple[int, int]]


@dataclass(frozen=True)
class LayoutZones:
    page_x: float
    page_y: float
    page_w: float
    page_h: float
    maze_x: float
    maze_y: float
    maze_w: float
    maze_h: float


def _difficulty_for_page(page_idx: int, total_pages: int) -> tuple[str, int, int, float]:
    progress = (page_idx + 1) / max(1, total_pages)
    if progress <= 0.30:
        return "Easy", 11, 14, 0.18
    if progress <= 0.70:
        return "Medium", 17, 22, 0.56
    return "Hard", 25, 32, 0.92


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


def _zones() -> LayoutZones:
    page_x = SAFE_LEFT
    page_y = SAFE_BOTTOM
    page_w = PAGE_W - SAFE_LEFT - SAFE_RIGHT
    page_h = PAGE_H - SAFE_TOP - SAFE_BOTTOM

    # Reference-style fixed composition:
    # start icon upper-left, maze upper-middle/right, finish icon lower-right.
    maze_x = page_x + (page_w * 0.18)
    maze_y = page_y + (page_h * 0.16)
    maze_w = page_w * 0.72
    maze_h = page_h * 0.70

    return LayoutZones(page_x, page_y, page_w, page_h, maze_x, maze_y, maze_w, maze_h)


def _draw_background(c: canvas.Canvas, bg: colors.Color, rng: random.Random, zones: LayoutZones) -> None:
    c.setFillColor(bg)
    c.rect(0, 0, PAGE_W, PAGE_H, fill=1, stroke=0)

    c.setStrokeColor(colors.HexColor("#1E293B"))
    c.setLineWidth(1.4)
    c.roundRect(zones.page_x - 8, zones.page_y - 8, zones.page_w + 16, zones.page_h + 16, 16, fill=0, stroke=1)

    for _ in range(22):
        c.setFillColor(colors.Color(1, 1, 1, alpha=0.10))
        c.circle(rng.uniform(20, PAGE_W - 20), rng.uniform(20, PAGE_H - 20), rng.uniform(5, 12), fill=1, stroke=0)


def _draw_bottom_page_no(c: canvas.Canvas, page_no: int) -> None:
    c.setFillColor(colors.HexColor("#334155"))
    c.setFont("Helvetica-Bold", 10)
    c.drawCentredString(PAGE_W / 2, SAFE_BOTTOM * 0.35, f"Page {page_no}")


def _title_block(c: canvas.Canvas, accent: colors.Color, puzzle_no: int, difficulty: str, theme_title: str, zones: LayoutZones) -> None:
    title_h = 44
    title_y = PAGE_H - SAFE_TOP - title_h

    c.setFillColor(accent)
    c.roundRect(zones.page_x, title_y, zones.page_w, title_h, 14, fill=1, stroke=0)

    c.setFillColor(colors.white)
    c.setFont("Helvetica-Bold", 17)
    c.drawString(zones.page_x + 16, title_y + 27, f"Puzzle {puzzle_no} • {difficulty}")

    c.setFillColor(colors.HexColor("#0F172A"))
    c.setFont("Helvetica-Bold", 28)
    c.drawString(zones.page_x, title_y - 34, theme_title)


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


def _draw_icon(c: canvas.Canvas, path: str, cx: float, cy: float, size: float) -> None:
    try:
        img = _prepare_icon_reader(path)
        w, h = _fit_image_box(img, size, size)
        c.drawImage(img, cx - (w / 2), cy - (h / 2), width=w, height=h, preserveAspectRatio=True, mask="auto")
    except Exception:
        c.setFillColor(colors.HexColor("#CBD5E1"))
        c.roundRect(cx - (size / 2), cy - (size / 2), size, size, 10, fill=1, stroke=0)


def _draw_decor(c: canvas.Canvas, zones: LayoutZones, style: str) -> None:
    cx = zones.maze_x + (zones.maze_w * 0.53)
    cy = zones.maze_y + (zones.maze_h * 0.44)
    size = PAGE_W * 0.11

    c.setLineWidth(2)
    if style == "stars":
        c.setStrokeColor(colors.HexColor("#7C3AED"))
        for dx, dy, r in [(-24, 20, 8), (0, 0, 10), (24, -16, 7)]:
            c.circle(cx + dx, cy + dy, r, fill=0, stroke=1)
    elif style == "fish":
        c.setStrokeColor(colors.HexColor("#0EA5E9"))
        c.ellipse(cx - size * 0.35, cy - size * 0.18, cx + size * 0.15, cy + size * 0.18, fill=0, stroke=1)
        c.line(cx + size * 0.15, cy, cx + size * 0.30, cy + size * 0.12)
        c.line(cx + size * 0.15, cy, cx + size * 0.30, cy - size * 0.12)
    elif style == "road":
        c.setStrokeColor(colors.HexColor("#334155"))
        c.roundRect(cx - size * 0.28, cy - size * 0.18, size * 0.56, size * 0.36, 8, fill=0, stroke=1)
        c.line(cx, cy - size * 0.15, cx, cy + size * 0.15)
    elif style == "yarn":
        c.setStrokeColor(colors.HexColor("#EC4899"))
        c.circle(cx, cy, size * 0.18, fill=0, stroke=1)
        c.circle(cx + 18, cy - 10, size * 0.08, fill=0, stroke=1)
    elif style == "signal":
        c.setStrokeColor(colors.HexColor("#16A34A"))
        c.line(cx, cy - size * 0.24, cx, cy + size * 0.24)
        c.circle(cx, cy + size * 0.14, size * 0.06, fill=0, stroke=1)


def _draw_maze(c: canvas.Canvas, maze: Maze, zones: LayoutZones, show_solution: bool, path: list[tuple[int, int]] | None, pair: IconPair) -> None:
    rows, cols = maze.rows, maze.cols
    cell = min(zones.maze_w / cols, zones.maze_h / rows)

    maze_w = cols * cell
    maze_h = rows * cell
    maze_x = zones.maze_x
    maze_y = zones.maze_y

    def box(cell_rc: tuple[int, int]) -> tuple[float, float, float, float]:
        r, cc = cell_rc
        x0 = maze_x + (cc * cell)
        y0 = maze_y + ((rows - 1 - r) * cell)
        return x0, y0, x0 + cell, y0 + cell

    c.setStrokeColor(colors.HexColor("#1F2937"))
    c.setLineWidth(max(0.85, cell * 0.10))
    for r in range(rows):
        for cc in range(cols):
            x0, y0, x1, y1 = box((r, cc))
            w = maze.walls[(r, cc)]
            if w["N"]:
                c.line(x0, y1, x1, y1)
            if w["S"]:
                c.line(x0, y0, x1, y0)
            if w["W"]:
                c.line(x0, y0, x0, y1)
            if w["E"]:
                c.line(x1, y0, x1, y1)

    c.setStrokeColor(colors.black)
    c.setLineWidth(max(2.2, cell * 0.24))
    for r in range(rows):
        for cc in range(cols):
            x0, y0, x1, y1 = box((r, cc))
            w = maze.walls[(r, cc)]
            if r == 0 and w["N"]:
                c.line(x0, y1, x1, y1)
            if r == rows - 1 and w["S"]:
                c.line(x0, y0, x1, y0)
            if cc == 0 and w["W"]:
                c.line(x0, y0, x0, y1)
            if cc == cols - 1 and w["E"]:
                c.line(x1, y0, x1, y1)

    # Fixed worksheet-style icon positions (Zone A and Zone C).
    start_x = zones.page_x + (zones.page_w * pair.start_pos[0])
    start_y = zones.page_y + (zones.page_h * pair.start_pos[1])
    finish_x = zones.page_x + (zones.page_w * pair.finish_pos[0])
    finish_y = zones.page_y + (zones.page_h * pair.finish_pos[1])

    start_size = PAGE_W * 0.20   # 18-24%
    finish_size = PAGE_W * 0.16  # 14-20%

    _draw_icon(c, str(pair.start_path), start_x, start_y, start_size)
    _draw_icon(c, str(pair.finish_path), finish_x, finish_y, finish_size)
    _draw_decor(c, zones, pair.decor_style)

    if show_solution and path:
        c.setStrokeColor(colors.HexColor("#DC2626"))
        c.setLineWidth(max(2.0, cell * 0.26))
        points = []
        for r, cc in path:
            x0, y0, _, _ = box((r, cc))
            points.append((x0 + (cell / 2), y0 + (cell / 2)))
        for i in range(len(points) - 1):
            c.line(*points[i], *points[i + 1])


def _unique_rng(seed: int, page: int, theme_key: str, difficulty: str, attempt: int) -> random.Random:
    h = sha1(f"{seed}|{page}|{theme_key}|{difficulty}|{attempt}".encode("utf-8")).hexdigest()
    return random.Random(int(h[:16], 16))


def build_book(output_file: str, pages: int, seed: int, title: str, icon_dir: str = "assets/icons") -> None:
    rng = random.Random(seed)
    c = canvas.Canvas(output_file, pagesize=A4)

    pairs = load_icon_pairs(icon_dir)
    plan = _icon_plan(pages, pairs, seed)
    bg_order = _palette_cycle((pages * 2) + 12, rng)
    zones = _zones()

    puzzles: List[PuzzlePage] = []
    seen_signatures: set[str] = set()

    for idx in range(pages):
        page_no = idx + 1
        pair = plan[idx]
        diff_name, rows, cols, diff_factor = _difficulty_for_page(idx, pages)

        maze = None
        solution: list[tuple[int, int]] = []
        sig = ""

        for attempt in range(42):
            prng = _unique_rng(seed, page_no, pair.key, diff_name, attempt)
            candidate = generate_maze(
                rows,
                cols,
                pair.key,
                diff_factor,
                prng,
                start_anchor=pair.start_anchor,
                end_anchor=pair.end_anchor,
            )
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
            maze = generate_maze(rows, cols, pair.key, diff_factor, prng, pair.start_anchor, pair.end_anchor)
            maze.difficulty = diff_name
            solution = solve_maze(maze)
            sig = maze_signature(maze)

        seen_signatures.add(sig)
        puzzles.append(PuzzlePage(page_no, pair, maze, solution))

        _draw_background(c, bg_order[idx], rng, zones)
        _title_block(c, ACCENTS[idx % len(ACCENTS)], page_no, diff_name, pair.title, zones)
        _draw_maze(c, maze, zones, show_solution=False, path=None, pair=pair)
        _draw_bottom_page_no(c, page_no)
        c.showPage()

    _draw_background(c, bg_order[pages], rng, zones)
    c.setFillColor(colors.HexColor("#0F172A"))
    c.setFont("Helvetica-Bold", 34)
    c.drawCentredString(PAGE_W / 2, PAGE_H * 0.62, "Solutions")
    _draw_bottom_page_no(c, pages + 1)
    c.showPage()

    for i, puzzle in enumerate(puzzles, start=1):
        _draw_background(c, bg_order[pages + i], rng, zones)
        _title_block(c, ACCENTS[(i - 1) % len(ACCENTS)], puzzle.puzzle_number, puzzle.maze.difficulty, puzzle.pair.title, zones)
        _draw_maze(c, puzzle.maze, zones, show_solution=True, path=puzzle.solution, pair=puzzle.pair)
        _draw_bottom_page_no(c, pages + i + 1)
        c.showPage()

    c.save()
