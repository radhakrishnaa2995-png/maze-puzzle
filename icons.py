"""Icon pairing and fixed layout metadata for premium scene maze books."""

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
    start_pos: tuple[float, float]   # normalized page-zone position
    finish_pos: tuple[float, float]  # normalized page-zone position
    decor_pos: tuple[float, float] | None
    start_scale: float
    finish_scale: float
    decor_scale: float | None
    decor_style: str


# Exact requested pairings.
_ICON_SPECS = [
    ("car", "Car Maze", "car.png", "car garage.png"),
    ("cat", "Cat Maze", "cat.png", "milk bowl.png"),
    ("rocket", "Rocket Maze", "rocket.jpg", "planet.jpg"),
    ("pirate", "Pirate Maze", "pirates ship.png", "treasure chest.png"),
    ("train", "Train Maze", "train.png", "train station.png"),
]

_THEME_DEFAULTS = {
    "car": {"start_anchor": "tl", "end_anchor": "br", "start_pos": (0.12, 0.74), "finish_pos": (0.86, 0.18), "decor_pos": (0.54, 0.47), "start_scale": 0.20, "finish_scale": 0.16, "decor_scale": 0.12, "decor_style": "road"},
    "cat": {"start_anchor": "left", "end_anchor": "right", "start_pos": (0.12, 0.52), "finish_pos": (0.86, 0.52), "decor_pos": (0.54, 0.44), "start_scale": 0.20, "finish_scale": 0.16, "decor_scale": 0.11, "decor_style": "yarn"},
    "rocket": {"start_anchor": "tl", "end_anchor": "br", "start_pos": (0.12, 0.76), "finish_pos": (0.86, 0.22), "decor_pos": (0.58, 0.50), "start_scale": 0.21, "finish_scale": 0.16, "decor_scale": 0.12, "decor_style": "stars"},
    "pirate": {"start_anchor": "tl", "end_anchor": "br", "start_pos": (0.12, 0.74), "finish_pos": (0.86, 0.18), "decor_pos": (0.56, 0.45), "start_scale": 0.22, "finish_scale": 0.16, "decor_scale": 0.12, "decor_style": "fish"},
    "train": {"start_anchor": "tl", "end_anchor": "br", "start_pos": (0.12, 0.74), "finish_pos": (0.86, 0.18), "decor_pos": (0.56, 0.44), "start_scale": 0.21, "finish_scale": 0.16, "decor_scale": 0.12, "decor_style": "signal"},
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
                start_anchor=d.get("start_anchor", "tl"),
                end_anchor=d.get("end_anchor", "br"),
                start_pos=d.get("start_pos", (0.12, 0.74)),
                finish_pos=d.get("finish_pos", (0.86, 0.18)),
                decor_pos=d.get("decor_pos", (0.56, 0.45)),
                start_scale=d.get("start_scale", 0.20),
                finish_scale=d.get("finish_scale", 0.16),
                decor_scale=d.get("decor_scale", 0.12),
                decor_style=d.get("decor_style", "road"),
            )
        )

    if not pairs:
        raise ValueError(f"No valid icon pairs found in {icon_dir}")

    print(f"Loaded {len(pairs)} icon pairs from {icon_dir}")
    for p in pairs:
        print(f" - {p.title}: {p.start_path.name} -> {p.finish_path.name}")

    return pairs
