"""Icon pairing metadata for scene maze puzzle pages."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import List


@dataclass(frozen=True)
class IconPair:
    title: str
    key: str
    start_path: Path
    finish_path: Path
    difficulty: str
    start_anchor: str
    end_anchor: str
    start_pos: tuple[float, float]
    finish_pos: tuple[float, float]
    decor_pos: tuple[float, float] | None
    start_scale: float
    finish_scale: float
    decor_scale: float | None


# Strict schema: (key, title, start_filename, finish_filename)
_ICON_SPECS = [
    ("car", "Car Maze", "car.png", "car garage.png"),
    ("cat", "Cat Maze", "cat.png", "milk bowl.png"),
    ("rocket", "Rocket Maze", "rocket.jpg", "planet.jpg"),
    ("pirate", "Pirate Maze", "pirates ship.png", "treasure chest.png"),
    ("train", "Train Maze", "train.png", "train station.png"),
]

# Fixed worksheet layout values shared across themes.
# Coordinates are normalized to full page in reportlab space (origin bottom-left).
_FIXED_LAYOUT = {
    "start_pos": (0.16, 0.74),
    "finish_pos": (0.84, 0.12),
    "start_scale": 0.20,
    "finish_scale": 0.16,
}


def load_icon_pairs(icon_dir: str = "assets/icons") -> List[IconPair]:
    root = Path(icon_dir)
    if not root.exists():
        raise FileNotFoundError(f"Icon directory not found: {icon_dir}")

    indexed = {p.name.lower(): p for p in root.rglob("*") if p.is_file()}

    invalid_specs = [row for row in _ICON_SPECS if len(row) != 4]
    if invalid_specs:
        for row in invalid_specs:
            print(f"Invalid _ICON_SPECS row (expected 4 values): {row}")
        raise ValueError("Invalid _ICON_SPECS configuration. Each row must contain 4 values.")

    pairs: List[IconPair] = []
    for key, title, start_name, finish_name in _ICON_SPECS:
        s = indexed.get(start_name.lower())
        f = indexed.get(finish_name.lower())

        if not s or not f:
            print(f"Skipping pair '{title}' (missing: {start_name if not s else ''} {finish_name if not f else ''})")
            continue

        pairs.append(
            IconPair(
                title=title,
                key=key,
                start_path=s,
                finish_path=f,
                difficulty="",
                start_anchor="tl",
                end_anchor="br",
                start_pos=_FIXED_LAYOUT["start_pos"],
                finish_pos=_FIXED_LAYOUT["finish_pos"],
                decor_pos=None,
                start_scale=_FIXED_LAYOUT["start_scale"],
                finish_scale=_FIXED_LAYOUT["finish_scale"],
                decor_scale=None,
            )
        )

    if not pairs:
        raise ValueError(f"No valid icon pairs found in {icon_dir}")

    print(f"Loaded {len(pairs)} icon pairs from {icon_dir}")
    return pairs
