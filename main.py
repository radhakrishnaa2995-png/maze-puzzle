# main.py
"""Entrypoint to generate one or more maze puzzle books."""

from __future__ import annotations

import json
import os
import secrets
import time

from pdf_builder import build_book

OUTPUT_DIR = "output"
CONFIG_FILE = "config.json"


def main() -> None:
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    with open(CONFIG_FILE, "r", encoding="utf-8") as fh:
        cfg = json.load(fh)

    books = int(cfg.get("books", 3))
    pages_per_book = int(cfg.get("pages_per_book", 30))
    shape_dir = str(cfg.get("shape_dir", "assets/shapes"))

    base_seed = (time.time_ns() ^ secrets.randbits(64)) & ((1 << 63) - 1)

    for idx in range(1, books + 1):
        book_seed = base_seed + (idx * 1_000_003)
        out_path = os.path.join(OUTPUT_DIR, f"Book_{idx}.pdf")
        title = f"Premium Maze Puzzle Book • Volume {idx}"
        build_book(
            output_file=out_path,
            pages=pages_per_book,
            seed=book_seed,
            title=title,
            shape_dir=shape_dir,
        )
        print(f"Generated {out_path}")


if __name__ == "__main__":
    main()
