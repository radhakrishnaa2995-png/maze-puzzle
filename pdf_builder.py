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
    colors.HexColor("#FADADD"),  # light pink
    colors.HexColor("#E6E6FA"),  # lavender
    colors.HexColor("#DDF1FF"),  # baby blue
    colors.HexColor("#DFF5E1"),  # mint green
    colors.HexColor("#FFF6DD"),  # cream
    colors.HexColor("#FFE6CC"),  # peach
]


@dataclass
class PuzzlePage:
    puzzle_number: int
    maze: Maze
    solution: list[tuple[int, int]]


def _draw_page_background(c: canvas.Canvas, bg: colors.Color, page_no: int, book_title: str) -> None:
    c.setFillColor(bg)
    c.rect(0, 0, PAGE_W, PAGE_H, fill=1, stroke=0)

    c.setFillColor(colors.white)
    c.roundRect(28, 28, PAGE_W - 56, PAGE_H - 56, 22, fill=1, stroke=0)

    c.setStrokeColor(colors.HexColor("#202020"))
    c.setLineWidth(2.6)
    c.roundRect(28, 28, PAGE_W - 56, PAGE_H - 56, 22, fill=0, stroke=1)

    c.setFillColor(colors.HexColor("#222222"))
    c.setFont("Helvetica-Bold", 13)
    c.drawString(45, PAGE_H - 44, book_title)

    c.setFont("Helvetica", 10)
    c.setFillColor(colors.HexColor("#4A4A4A"))
    c.drawRightString(PAGE_W - 45, PAGE_H - 44, f"Page {page_no}")


def _draw_maze(
    c: canvas.Canvas,
    maze: Maze,
    frame_x: float,
    frame_y: float,
    frame_w: float,
    frame_h: float,
    show_solution: bool = False,
    solution_path: list[tuple[int, int]] | None = None,
) -> None:
    cell = min(frame_w / maze.cols, frame_h / maze.rows)
    origin_x = frame_x + (frame_w - maze.cols * cell) / 2
    origin_y = frame_y + (frame_h - maze.rows * cell) / 2

    c.setStrokeColor(colors.black)
    c.setLineWidth(1.55)
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
        rad = max(7, min(11, cell * 0.32))
        c.setFillColor(fill)
        c.circle(cx, cy, rad, fill=1, stroke=0)
        c.setFillColor(colors.white)
        c.setFont("Helvetica-Bold", max(8, int(rad)))
        c.drawCentredString(cx, cy - rad * 0.35, label)

    marker(maze.start, "S", colors.HexColor("#2E8B57"))
    marker(maze.end, "F", colors.HexColor("#E74C3C"))

    if show_solution and solution_path:
        c.setStrokeColor(colors.HexColor("#4C6EF5"))
        c.setLineWidth(max(2.0, cell * 0.22))
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
        return "Easy", 17, 17, 0.15
    if ratio < 0.66:
        return "Medium", 23, 23, 0.5
    return "Hard", 31, 31, 0.85


def build_book(output_file: str, pages: int, seed: int, title: str) -> None:
    rng = random.Random(seed)
    c = canvas.Canvas(output_file, pagesize=A4)

    shape_order = shape_sequence(pages, rng)
    backgrounds = palette_sequence((pages * 2) + 2, PASTEL_PALETTE, rng)

    puzzles: List[PuzzlePage] = []

    for page in range(1, pages + 1):
        bg = backgrounds[page - 1]
        _draw_page_background(c, bg, page_no=page, book_title=title)

        difficulty, rows, cols, difficulty_factor = _difficulty_for_page(page - 1, pages)
        shape = shape_order[page - 1]
        maze = generate_maze(rows=rows, cols=cols, shape=shape, difficulty_factor=difficulty_factor, rng=rng)
        maze.difficulty = difficulty
        solution = solve_maze(maze)
        puzzles.append(PuzzlePage(page, maze, solution))

        c.setFillColor(colors.HexColor("#1F2937"))
        c.setFont("Helvetica-Bold", 18)
        c.drawString(48, PAGE_H - 78, f"Puzzle {page}: {shape} Maze")

        c.setFont("Helvetica", 12)
        c.setFillColor(colors.HexColor("#4B5563"))
        c.drawString(48, PAGE_H - 98, f"Difficulty: {difficulty}")
        c.drawRightString(PAGE_W - 48, PAGE_H - 98, "Find a path from S to F")

        _draw_maze(c, maze, frame_x=56, frame_y=96, frame_w=PAGE_W - 112, frame_h=PAGE_H - 190)
        c.showPage()

    # Solution section
    for idx, puzzle in enumerate(puzzles, start=1):
        bg = backgrounds[pages + idx - 1]
        _draw_page_background(c, bg, page_no=pages + idx, book_title=f"{title} • Solutions")

        c.setFillColor(colors.HexColor("#0F172A"))
        c.setFont("Helvetica-Bold", 17)
        c.drawString(48, PAGE_H - 78, f"Solution {puzzle.puzzle_number}: {puzzle.maze.shape} Maze")

        c.setFont("Helvetica", 11)
        c.setFillColor(colors.HexColor("#475569"))
        c.drawString(48, PAGE_H - 98, "Highlighted route shows the correct answer.")

        _draw_maze(
            c,
            puzzle.maze,
            frame_x=56,
            frame_y=96,
            frame_w=PAGE_W - 112,
            frame_h=PAGE_H - 190,
            show_solution=True,
            solution_path=puzzle.solution,
        )
        c.showPage()

    c.save()
