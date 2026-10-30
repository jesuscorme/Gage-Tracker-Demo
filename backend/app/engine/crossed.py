"""Data structure shared by the crossed GRR designs: every operator measures every part
``trials`` times (balanced full factorial). Returns Y[operator, trial, part]."""

import numpy as np

from app.engine.common import Checker, balanced_cells, check_count, number, require_full_factorial, tolerance_of

KEYS = ("operator", "part", "trial")


def parse(data: dict, *, min_parts=2, max_parts=None, min_ops=2, max_ops=None, min_trials=2, max_trials=None):
    chk = Checker()
    design, obs = data.get("design") or {}, data.get("observations") or []
    if not obs:
        chk.add("no_data", "the study has no observations")
        chk.raise_if_any()
    cells = balanced_cells(chk, obs, KEYS)
    ops, parts, trials = require_full_factorial(chk, cells, KEYS)
    check_count(chk, design, "operators", len(ops), min_ops, max_ops)
    check_count(chk, design, "parts", len(parts), min_parts, max_parts)
    check_count(chk, design, "trials", len(trials), min_trials, max_trials)
    tol = tolerance_of(chk, design)
    resolution = number(design.get("resolution"))
    chk.raise_if_any()
    y = np.array([[[cells[(o, p, t)] for p in parts] for t in trials] for o in ops], dtype=float)
    return chk, y, ops, parts, trials, tol, resolution


def charts(y: np.ndarray, ops, parts, d2_ranges: dict, a2: float, d3: float, d4: float) -> dict:
    """Range and average charts per operator plus the part x operator interaction plot."""
    ranges = y.max(axis=1) - y.min(axis=1)          # [op, part]
    means = y.mean(axis=1)                          # [op, part]
    rbar = float(ranges.mean())
    xbarbar = float(y.mean())
    return {
        "range_chart": {"operators": ops, "parts": parts, "values": ranges.tolist(),
                        "center": rbar, "ucl": d4 * rbar, "lcl": d3 * rbar},
        "average_chart": {"operators": ops, "parts": parts, "values": means.tolist(),
                          "center": xbarbar, "ucl": xbarbar + a2 * rbar, "lcl": xbarbar - a2 * rbar},
        "interaction": {"operators": ops, "parts": parts, "values": means.tolist()},
        "by_operator": {"operators": ops, "values": [y[i].ravel().tolist() for i in range(len(ops))]},
        "by_part": {"parts": parts, "means": y.mean(axis=(0, 1)).tolist()},
    }


def resolution_metric(resolution, tol, metrics: dict) -> None:
    metrics["resolution_pct_tolerance"] = (100.0 * resolution / tol) if resolution and tol else None
