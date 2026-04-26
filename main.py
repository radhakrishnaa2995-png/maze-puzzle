# main.py
"""Entry point for generating multiple maze puzzle books."""

from __future__ import annotations

import json
import os
import random
import time

from pdf_builder import build_book

OUTPUT_DIR = "output"
CONFIG_FILE = "config.json"


def main() -> None:
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    with open(CONFIG_FILE, "r", encoding="utf-8") as f:
        cfg = json.load(f)

    books = int(cfg.get("books", 5))
    pages_per_book = int(cfg.get("pages_per_book", 25))
    shape_dir = cfg.get("shape_dir", "assets/shapes")

    base_seed = int(time.time() * 1000) ^ random.SystemRandom().randint(1, 10_000_000)

    for i in range(1, books + 1):
        book_seed = base_seed + (i * 99_991)
        file_path = os.path.join(OUTPUT_DIR, f"Book_{i}.pdf")
        title = f"Maze Puzzle Book for Kids • Volume {i}"
        build_book(output_file=file_path, pages=pages_per_book, seed=book_seed, title=title, shape_dir=shape_dir)
        print(f"Generated {file_path}")


if __name__ == "__main__":
    main()
