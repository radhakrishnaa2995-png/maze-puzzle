# main.py
"""Entrypoint for premium Scene Maze Puzzle Book PDF generation."""

from __future__ import annotations

import json
import os
import secrets
import time

from icons import load_icon_pairs
from pdf_builder import build_book

OUTPUT_DIR = "output"
CONFIG_FILE = "config.json"
OUTPUT_FILE = "Scene_Maze_Puzzle_Book.pdf"


def main() -> None:
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    with open(CONFIG_FILE, "r", encoding="utf-8") as fh:
        cfg = json.load(fh)

    icon_dir = str(cfg.get("icon_dir", "assets/icons"))
    pages_per_book = int(cfg.get("pages_per_book", 15))
    layout_mode = str(cfg.get("layout_mode", "flow_masked"))

    pairs = load_icon_pairs(icon_dir)
    pages = max(len(pairs), max(1, pages_per_book))

    seed = (time.time_ns() ^ secrets.randbits(64)) & ((1 << 63) - 1)
    out_path = os.path.join(OUTPUT_DIR, OUTPUT_FILE)

    build_book(
        output_file=out_path,
        pages=pages,
        seed=seed,
        title="Scene Maze Puzzle Book",
        icon_dir=icon_dir,
    )

    print(f"Layout mode: {layout_mode}")
    print(f"Generated {out_path}")


if __name__ == "__main__":
    main()
