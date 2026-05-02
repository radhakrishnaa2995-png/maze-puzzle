    # Keep silhouettes organic with edge notches.
    carve_count = {"easy": 2, "medium": 3, "hard": 4}.get(profile, 3)
    for _ in range(carve_count):
        side = rng.choice(["N", "S", "W", "E"])
        depth = rng.randint(1, max(2, rows // 12 if side in {"N", "S"} else cols // 12))
        span = rng.randint(
            max(3, cols // 10 if side in {"N", "S"} else rows // 10),
            max(4, cols // 4 if side in {"N", "S"} else rows // 4),
        )
        if side in {"N", "S"}:
            start_c = rng.randint(1, max(1, cols - span - 1))
            rr = range(0, depth) if side == "N" else range(rows - depth, rows)
            for r in rr:
                for c in range(start_c, min(cols - 1, start_c + span)):
                    allowed.discard((r, c))
        else:
            start_r = rng.randint(1, max(1, rows - span - 1))
            cc = range(0, depth) if side == "W" else range(cols - depth, cols)
            for c in cc:
                for r in range(start_r, min(rows - 1, start_r + span)):
                    allowed.discard((r, c))

    return allowed
