# main.py
"""Entrypoint for premium Scene Maze Puzzle Book PDF generation."""

from _future_ import annotations

import json
import os
import secrets
import time

from icons import load_icon_pairs
from pdf_builder import build_book

OUTPUT_DIR = "output"
CONFIG_FILE = "config.json"
OUTPUT_FILE = "Maze_Puzzle_Book.pdf"


def main() -> None:
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    with open(CONFIG_FILE, "r", encoding="utf-8") as fh:
        cfg = json.load(fh)

    icon_dir = str(cfg.get("icon_dir", "assets/icons"))
    pages_per_book = int(cfg.get("pages_per_book", 15))

    pairs = load_icon_pairs(icon_dir)
    pages = max(len(pairs), max(1, pages_per_book))

    seed = (time.time_ns() ^ secrets.randbits(64)) & ((1 << 63) - 1)
    output_file = str(cfg.get("output_file", OUTPUT_FILE))
    out_path = os.path.join(OUTPUT_DIR, output_file)
    difficulty_profiles = cfg.get("difficulty_profiles", {})
    icon_scale = float(cfg.get("icon_scale", 0.2))
    anchor_cycle = cfg.get(
        "entry_exit_cycle",
        [["tl", "br"], ["tr", "bl"], ["left", "right"], ["top", "bottom"]],
    )

    build_book(
        output_file=out_path,
        pages=pages,
        seed=seed,
        title="Scene Maze Puzzle Book",
        icon_dir=icon_dir,
        difficulty_profiles=difficulty_profiles,
        icon_scale=icon_scale,
        anchor_cycle=anchor_cycle,
    )

    print(f"Generated {out_path}")


if _name_ == "_main_":
    main()
