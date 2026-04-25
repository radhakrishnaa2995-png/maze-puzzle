"""PDF composition for printable maze books."""

from __future__ import annotations

import random
from dataclasses import dataclass
from typing import List

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

from maze_generator import Maze, generate_maze
from shapes import palette_sequence, shape_sequence
from solver import solve_maze

PAGE_W, PAGE_H = A4

PASTEL_PALETTE = [
    colors.HexColor("#FADADD"),
    colors.HexColor("#E6E6FA"),
    colors.HexColor("#DDF1FF"),
    colors.HexColor("#DFF5E1"),
    colors.HexColor("#FFF6DD"),
    colors.HexColor("#FFE6CC"),
]

ACCENTS = [
    colors.HexColor("#8B5CF6"),
    colors.HexColor("#14B8A6"),
    colors.HexColor("#F97316"),
    colors.HexColor("#3B82F6"),
]


@dataclass
class PuzzlePage:
    puzzle_number: int
    maze: Maze
    solution: list[tuple[int, int]]


def _draw_page_background(c: canvas.Canvas, bg: colors.Color, page_no: int, book_title: str, rng: random.Random) -> None:
    c.setFillColor(bg)
    c.rect(0, 0, PAGE_W, PAGE_H, fill=1, stroke=0)

    # Soft decorative bubbles for playful kid-friendly look.
    for _ in range(20):
        col = rng.choice(PASTEL_PALETTE)
        c.setFillColor(colors.Color(col.red, col.green, col.blue, alpha=0.25))
        r = rng.uniform(8, 26)
        x = rng.uniform(40, PAGE_W - 40)
        y = rng.uniform(40, PAGE_H - 40)
        c.circle(x, y, r, stroke=0, fill=1)

    c.setFillColor(colors.white)
    c.roundRect(25, 25, PAGE_W - 50, PAGE_H - 50, 24, fill=1, stroke=0)

    c.setStrokeColor(colors.HexColor("#111111"))
    c.setLineWidth(3)
    c.roundRect(25, 25, PAGE_W - 50, PAGE_H - 50, 24, fill=0, stroke=1)

    c.setFillColor(colors.HexColor("#1F2937"))
    c.setFont("Helvetica-Bold", 13)
    c.drawString(42, PAGE_H - 42, book_title)

    c.setFillColor(colors.HexColor("#374151"))
    c.setFont("Helvetica", 10)
    c.drawRightString(PAGE_W - 42, PAGE_H - 42, f"Page {page_no}")


def _edge_port_center(
    maze: Maze,
    side: str,
    cell_rc: tuple[int, int],
    origin_x: float,
    origin_y: float,
    cell: float,
) -> tuple[float, float]:
    rr, cc = cell_rc
    x0 = origin_x + cc * cell
    y0 = origin_y + (maze.rows - 1 - rr) * cell
    x1, y1 = x0 + cell, y0 + cell

    if side == "N":
        return (x0 + cell / 2, y1)
    if side == "S":
        return (x0 + cell / 2, y0)
    if side == "W":
        return (x0, y0 + cell / 2)
    return (x1, y0 + cell / 2)


def _draw_maze(
    c: canvas.Canvas,
    maze: Maze,
    frame_x: float,
    frame_y: float,
    frame_w: float,
    frame_h: float,
    accent: colors.Color,
    show_solution: bool = False,
    solution_path: list[tuple[int, int]] | None = None,
) -> None:
    cell = min(frame_w / maze.cols, frame_h / maze.rows)
    origin_x = frame_x + (frame_w - maze.cols * cell) / 2
    origin_y = frame_y + (frame_h - maze.rows * cell) / 2

    c.setStrokeColor(colors.HexColor("#121212"))
    c.setLineWidth(1.6)
    c.setLineCap(1)

    for r in range(maze.rows):
        for col in range(maze.cols):
            cell_idx = (r, col)
            if cell_idx not in maze.active_cells:
                continue

            walls = maze.walls[cell_idx]
            x0, y0 = origin_x + col * cell, origin_y + (maze.rows - 1 - r) * cell
            x1, y1 = x0 + cell, y0 + cell

            if walls["N"]:
                c.line(x0, y1, x1, y1)
            if walls["S"]:
                c.line(x0, y0, x1, y0)
            if walls["W"]:
                c.line(x0, y0, x0, y1)
            if walls["E"]:
                c.line(x1, y0, x1, y1)

    def marker(cell_rc: tuple[int, int], label: str, fill: colors.Color) -> None:
        rr, cc = cell_rc
        cx = origin_x + cc * cell + cell / 2
        cy = origin_y + (maze.rows - 1 - rr) * cell + cell / 2
        rad = max(7.5, min(12, cell * 0.35))
        c.setFillColor(fill)
        c.circle(cx, cy, rad, fill=1, stroke=0)
        c.setFillColor(colors.white)
        c.setFont("Helvetica-Bold", max(8, int(rad)))
        c.drawCentredString(cx, cy - rad * 0.35, label)

    marker(maze.start, "S", colors.HexColor("#16A34A"))
    marker(maze.end, "F", colors.HexColor("#DC2626"))

    # Draw explicit entrance/exit pointers so openings are obvious.
    for cell_rc, side, label, fill in [
        (maze.start, maze.start_open_side, "ENTRY", colors.HexColor("#16A34A")),
        (maze.end, maze.end_open_side, "EXIT", colors.HexColor("#DC2626")),
    ]:
        px, py = _edge_port_center(maze, side, cell_rc, origin_x, origin_y, cell)
        dx, dy = 0.0, 0.0
        if side == "N":
            dy = 20
        elif side == "S":
            dy = -20
        elif side == "W":
            dx = -28
        else:
            dx = 28

        c.setStrokeColor(fill)
        c.setLineWidth(2.6)
        c.line(px, py, px + dx * 0.6, py + dy * 0.6)

        c.setFillColor(fill)
        c.roundRect(px + dx - 18, py + dy - 7, 36, 14, 5, stroke=0, fill=1)
        c.setFillColor(colors.white)
        c.setFont("Helvetica-Bold", 7)
        c.drawCentredString(px + dx, py + dy - 2.8, label)

    if show_solution and solution_path:
        c.setStrokeColor(colors.Color(accent.red, accent.green, accent.blue, alpha=0.95))
        c.setLineWidth(max(2.2, cell * 0.26))
        pts = []
        for rr, cc in solution_path:
            px = origin_x + cc * cell + cell / 2
            py = origin_y + (maze.rows - 1 - rr) * cell + cell / 2
            pts.append((px, py))
        for i in range(len(pts) - 1):
            c.line(*pts[i], *pts[i + 1])


def _difficulty_for_page(page_index: int, total_pages: int) -> tuple[str, int, int, float]:
    ratio = page_index / max(1, total_pages - 1)
    if ratio < 0.33:
        return "Easy", 17, 17, 0.18
    if ratio < 0.66:
        return "Medium", 23, 23, 0.5
    return "Hard", 31, 31, 0.88


def build_book(output_file: str, pages: int, seed: int, title: str) -> None:
    rng = random.Random(seed)
    c = canvas.Canvas(output_file, pagesize=A4)

    shape_order = shape_sequence(pages, rng)
    backgrounds = palette_sequence((pages * 2) + 2, PASTEL_PALETTE, rng)

    puzzles: List[PuzzlePage] = []

    for page in range(1, pages + 1):
        bg = backgrounds[page - 1]
        accent = ACCENTS[(page - 1) % len(ACCENTS)]
        _draw_page_background(c, bg, page_no=page, book_title=title, rng=rng)

        difficulty, rows, cols, difficulty_factor = _difficulty_for_page(page - 1, pages)
        shape = shape_order[page - 1]
        maze = generate_maze(rows=rows, cols=cols, shape=shape, difficulty_factor=difficulty_factor, rng=rng)
        maze.difficulty = difficulty
        solution = solve_maze(maze)
        puzzles.append(PuzzlePage(page, maze, solution))

        c.setFillColor(accent)
        c.roundRect(42, PAGE_H - 90, 180, 24, 8, stroke=0, fill=1)
        c.setFillColor(colors.white)
        c.setFont("Helvetica-Bold", 13)
        c.drawString(52, PAGE_H - 82, f"Puzzle {page} • {difficulty}")

        c.setFillColor(colors.HexColor("#1F2937"))
        c.setFont("Helvetica-Bold", 18)
        c.drawString(42, PAGE_H - 112, f"{shape} Maze")

        c.setFillColor(colors.HexColor("#4B5563"))
        c.setFont("Helvetica", 11)
        c.drawRightString(PAGE_W - 42, PAGE_H - 110, "Start at ENTRY and reach EXIT")

        _draw_maze(
            c,
            maze,
            frame_x=52,
            frame_y=90,
            frame_w=PAGE_W - 104,
            frame_h=PAGE_H - 190,
            accent=accent,
        )
        c.showPage()

    for idx, puzzle in enumerate(puzzles, start=1):
        bg = backgrounds[pages + idx - 1]
        accent = ACCENTS[(idx - 1) % len(ACCENTS)]
        _draw_page_background(c, bg, page_no=pages + idx, book_title=f"{title} • Solutions", rng=rng)

        c.setFillColor(accent)
        c.roundRect(42, PAGE_H - 90, 210, 24, 8, stroke=0, fill=1)
        c.setFillColor(colors.white)
        c.setFont("Helvetica-Bold", 13)
        c.drawString(52, PAGE_H - 82, f"Solution {puzzle.puzzle_number} • {puzzle.maze.difficulty}")

        c.setFillColor(colors.HexColor("#0F172A"))
        c.setFont("Helvetica-Bold", 17)
        c.drawString(42, PAGE_H - 112, f"{puzzle.maze.shape} Maze")

        c.setFillColor(colors.HexColor("#475569"))
        c.setFont("Helvetica", 11)
        c.drawString(42, PAGE_H - 127, "Highlighted route shows the correct path from entry to exit.")

        _draw_maze(
            c,
            puzzle.maze,
            frame_x=52,
            frame_y=90,
            frame_w=PAGE_W - 104,
            frame_h=PAGE_H - 190,
            accent=accent,
            show_solution=True,
            solution_path=puzzle.solution,
        )
        c.showPage()

    c.save()
