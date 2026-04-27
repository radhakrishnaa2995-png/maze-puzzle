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


_ICON_SPECS = [
    ("car", "Car Maze", "car.png", "car garage.png"),
    ("cat", "Cat Maze", "cat.png", "milk bowl.png"),
    ("rocket", "Rocket Maze", "rocket.jpg", "planet.jpg"),
    ("pirate", "Pirate Maze", "pirates ship.png", "treasure chest.png"),
    ("train", "Train Maze", "train station.png"),
]

# Worksheet-style fixed layout defaults.
_THEME_DEFAULTS = {
    "car": {"start_pos": (0.12, 0.76), "finish_pos": (0.86, 0.16), "start_scale": 0.21, "finish_scale": 0.16},
    "cat": {"start_pos": (0.12, 0.76), "finish_pos": (0.86, 0.16), "start_scale": 0.21, "finish_scale": 0.16},
    "rocket": {"start_pos": (0.12, 0.76), "finish_pos": (0.86, 0.17), "start_scale": 0.22, "finish_scale": 0.17},
    "pirate": {"start_pos": (0.12, 0.76), "finish_pos": (0.86, 0.15), "start_scale": 0.23, "finish_scale": 0.17},
    "train": {"start_pos": (0.12, 0.76), "finish_pos": (0.86, 0.16), "start_scale": 0.22, "finish_scale": 0.17},
}


def load_icon_pairs(icon_dir: str = "assets/icons") -> List[IconPair]:
    root = Path(icon_dir)
    if not root.exists():
        raise FileNotFoundError(f"Icon directory not found: {icon_dir}")

    indexed = {p.name.lower(): p for p in root.rglob("*") if p.is_file()}

    pairs: List[IconPair] = []
    for key, title, start_name, finish_name in _ICON_SPECS:
        s = indexed.get(start_name.lower())
        f = indexed.get(finish_name.lower())

        if not s or not f:
            print(f"Skipping pair '{title}' (missing: {start_name if not s else ''} {finish_name if not f else ''})")
            continue

        d = _THEME_DEFAULTS.get(key, {})
        pairs.append(
            IconPair(
                title=title,
                key=key,
                start_path=s,
                finish_path=f,
                difficulty="",
                start_anchor="tl",
                end_anchor="br",
                start_pos=d.get("start_pos", (0.12, 0.76)),
                finish_pos=d.get("finish_pos", (0.86, 0.16)),
                decor_pos=None,
                start_scale=d.get("start_scale", 0.21),
                finish_scale=d.get("finish_scale", 0.16),
                decor_scale=None,
            )
        )

    if not pairs:
        raise ValueError(f"No valid icon pairs found in {icon_dir}")

    print(f"Loaded {len(pairs)} icon pairs from {icon_dir}")
    return pairs
