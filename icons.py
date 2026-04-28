"""Icon pairing metadata for scene maze puzzle pages."""

from __future__ import annotations

import re
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


# Fixed worksheet layout values shared across themes.
# Coordinates are normalized to full page in reportlab space (origin bottom-left).
_FIXED_LAYOUT = {
    "start_pos": (0.16, 0.74),
    "finish_pos": (0.84, 0.12),
    "start_scale": 0.20,
    "finish_scale": 0.16,
}

_SUPPORTED_EXTS = {".png", ".jpg", ".jpeg"}

# Priority logical mappings (left -> right), using normalized stem names.
_PRIORITY_SPECS: list[tuple[str, str]] = [
    # TRANSPORT / PLACE
    ("car", "car garage"),
    ("train", "train station"),
    ("school bus", "school"),
    # SPACE / ADVENTURE
    ("rocket", "planet"),
    ("pirates ship", "treasure chest"),
    # PROFESSIONS / BUILDINGS
    ("doctor", "hospital"),
    ("fire truck", "fire house"),
    # ANIMALS / OBJECTS
    ("dog", "bone"),
    ("cat", "milk bowl"),
    ("monkey", "banana"),
    ("bird", "nest"),
    ("bee", "flower"),
    ("rabbit", "carrot"),
    # KIDS / PLAY
    ("kid with ball", "playground"),
    ("kid", "candy"),
    # MAGIC / FANTASY
    ("wizard", "magic wand"),
    ("unicorn", "rainbow"),
    # SEASON / SCENE
    ("snowman", "winterland"),
    ("butterfly", "garden"),
    # EXTRA SCENE
    ("ship", "beach"),
]


def _normalize_name(name: str) -> str:
    base = Path(name).stem.lower()
    base = re.sub(r"[_\-]+", " ", base)
    base = re.sub(r"\s+", " ", base).strip()
    return base


def _display_name(name: str) -> str:
    return " ".join(part.capitalize() for part in name.split())


def _story_title(start: str, end: str) -> tuple[str, str, str]:
    key = f"{start.replace(' ', '_')}_to_{end.replace(' ', '_')}"
    title = f"{_display_name(start)} Maze"
    story = f"HELP THE {start.upper()} REACH THE {end.upper()}!"
    return key, title, story


def _pick_exact_or_contains(
    indexed: dict[str, list[Path]],
    used_icons: set[Path],
    wanted: str,
) -> Path | None:
    # exact match first
    candidates = indexed.get(wanted, [])
    for p in candidates:
        if p not in used_icons:
            return p

    # contains fallback
    for stem, paths in indexed.items():
        if wanted in stem:
            for p in paths:
                if p not in used_icons:
                    return p
    return None


def load_icon_pairs(icon_dir: str = "assets/icons") -> List[IconPair]:
    root = Path(icon_dir)
    if not root.exists():
        raise FileNotFoundError(f"Icon directory not found: {icon_dir}")

    # Load ALL icons (png/jpg/jpeg), sorted for consistency.
    all_icons = sorted(
        [p for p in root.rglob("*") if p.is_file() and p.suffix.lower() in _SUPPORTED_EXTS],
        key=lambda p: (p.name.lower(), str(p).lower()),
    )
    if not all_icons:
        raise ValueError(f"No icons found in {icon_dir}")

    indexed: dict[str, list[Path]] = {}
    for p in all_icons:
        n = _normalize_name(p.name)
        indexed.setdefault(n, []).append(p)

    used_icons: set[Path] = set()
    pairs: List[IconPair] = []

    # 1) Priority logical pairing, no-repeat.
    for start_name, end_name in _PRIORITY_SPECS:
        s = _pick_exact_or_contains(indexed, used_icons, _normalize_name(start_name))
        f = _pick_exact_or_contains(indexed, used_icons, _normalize_name(end_name))
        if s is None or f is None or s == f:
            continue
        used_icons.add(s)
        used_icons.add(f)

        key, title, _story = _story_title(_normalize_name(start_name), _normalize_name(end_name))
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

    # 2) Pair remaining icons sequentially, no-repeat.
    remaining = [p for p in all_icons if p not in used_icons]
    for i in range(0, len(remaining) - 1, 2):
        s = remaining[i]
        f = remaining[i + 1]
        used_icons.add(s)
        used_icons.add(f)

        s_name = _normalize_name(s.name)
        f_name = _normalize_name(f.name)
        key, title, _story = _story_title(s_name, f_name)

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
        raise ValueError(f"No valid icon pairs could be formed from {icon_dir}")

    print(f"Loaded {len(all_icons)} icons and built {len(pairs)} unique pairs from {icon_dir}")
    return pairs
