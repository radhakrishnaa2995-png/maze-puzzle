# main.py
"""Entrypoint to generate a single premium maze puzzle book PDF."""

from __future__ import annotations

import json
import os
import secrets
import time

from pdf_builder import build_book
from shapes import all_shape_names, load_shapes

OUTPUT_DIR = "output"
CONFIG_FILE = "config.json"
OUTPUT_FILE = "Maze_Puzzle_Book.pdf"


def main() -> None:
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    with open(CONFIG_FILE, "r", encoding="utf-8") as fh:
        cfg = json.load(fh)

    shape_dir = str(cfg.get("shape_dir", "assets/shapes"))
    orientation_mode = str(cfg.get("orientation_mode", "original"))
    if orientation_mode != "original":
        raise ValueError("orientation_mode must be 'original'")

    loaded = load_shapes(shape_dir, orientation_mode)
    if not loaded:
        raise RuntimeError(f"No usable shapes loaded from {shape_dir}")

    shapes_count = len(all_shape_names(shape_dir, orientation_mode))
    # One unique shape per page; no repeats.
    pages = shapes_count

    seed = (time.time_ns() ^ secrets.randbits(64)) & ((1 << 63) - 1)

    out_path = os.path.join(OUTPUT_DIR, OUTPUT_FILE)
    build_book(
        output_file=out_path,
        pages=pages,
        seed=seed,
        title="Maze Puzzle Book for Kids",
        shape_dir=shape_dir,
        orientation_mode=orientation_mode,
    )
    print(f"Generated {out_path}")


if __name__ == "__main__":
    main()
