# main.py
"""Entrypoint to generate a single maze puzzle book PDF."""

from __future__ import annotations

import json
import os
import secrets
import time

from pdf_builder import build_book
from shapes import all_shape_names

OUTPUT_DIR = "output"
CONFIG_FILE = "config.json"
OUTPUT_FILE = "Maze_Puzzle_Book.pdf"


def main() -> None:
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    with open(CONFIG_FILE, "r", encoding="utf-8") as fh:
        cfg = json.load(fh)

    shape_dir = str(cfg.get("shape_dir", "assets/shapes"))
    shapes_count = len(all_shape_names(shape_dir))

    configured_pages = int(cfg.get("pages_per_book", 0))
    pages = max(configured_pages, shapes_count)

    seed = (time.time_ns() ^ secrets.randbits(64)) & ((1 << 63) - 1)

    out_path = os.path.join(OUTPUT_DIR, OUTPUT_FILE)
    build_book(
        output_file=out_path,
        pages=pages,
        seed=seed,
        title="Maze Puzzle Book for Kids",
        shape_dir=shape_dir,
    )
    print(f"Generated {out_path}")


if __name__ == "__main__":
    main()
