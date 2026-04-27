"""Icon pairing and loading helpers for premium scene maze books."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import List


@dataclass(frozen=True)
class IconPair:
    key: str
    title: str
    start_label: str
    finish_label: str
    start_path: Path
    finish_path: Path
    start_anchor: str
    end_anchor: str


# Exact requested pairings and deliberate visual anchor layouts.
_ICON_SPECS = [
    ("car", "Car Maze", "car.png", "car garage.png", "left", "right"),
    ("cat", "Cat Maze", "cat.png", "milk bowl.png", "tl", "br"),
    ("rocket", "Rocket Maze", "rocket.jpg", "planet.jpg", "tl", "br"),
    ("pirate", "Pirate Maze", "pirates ship.png", "treasure chest.png", "tl", "br"),
    ("train", "Train Maze", "train.png", "train station.png", "bl", "tr"),
]


def load_icon_pairs(icon_dir: str = "assets/icons") -> List[IconPair]:
    root = Path(icon_dir)
    if not root.exists():
        raise FileNotFoundError(f"Icon directory not found: {icon_dir}")

    indexed = {p.name.lower(): p for p in root.rglob("*") if p.is_file()}

    pairs: List[IconPair] = []
    for key, title, start_name, finish_name, start_anchor, end_anchor in _ICON_SPECS:
        s = indexed.get(start_name.lower())
        f = indexed.get(finish_name.lower())

        if not s or not f:
            print(f"Skipping pair '{title}' (missing: {start_name if not s else ''} {finish_name if not f else ''})")
            continue

        pairs.append(
            IconPair(
                key=key,
                title=title,
                start_label=start_name,
                finish_label=finish_name,
                start_path=s,
                finish_path=f,
                start_anchor=start_anchor,
                end_anchor=end_anchor,
            )
        )

    if not pairs:
        raise ValueError(f"No valid icon pairs found in {icon_dir}")

    print(f"Loaded {len(pairs)} icon pairs from {icon_dir}")
    for p in pairs:
        print(f" - {p.title}: {p.start_path.name} -> {p.finish_path.name}")

    return pairs
