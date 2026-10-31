"""Crossed Gage R&R, Average and Range method (AIAG MSA 4th ed., Chapter III Section B).

Model: the method estimates repeatability from the average within-cell range and
reproducibility from the range of operator averages. It does not separate the
operator x part interaction (use the ANOVA method for that).
"""

import numpy as np

from app.engine import constants as C
from app.engine.common import clean, grr_indicators, study_multiplier
from app.engine.crossed import charts, parse, resolution_metric

METHOD = "GRR_CROSSED_AR"
VERSION = "1.0.0"


def calculate(data: dict) -> dict:
    params = data.get("params") or {}
    chk, y, ops, parts, trials, tol, resolution = parse(
        data, max_parts=10, max_ops=3, max_trials=3)
    k = study_multiplier(chk, params)
    chk.raise_if_any()
    o, r, p = y.shape
    warnings: list[str] = []
    if o * p <= 15:
        warnings.append("K1 is tabulated for parts x operators > 15; with fewer cells EV is an approximation")

    ranges = y.max(axis=1) - y.min(axis=1)              # [op, part]
    rbar_op = ranges.mean(axis=1)                       # per operator
    xbar_op = y.mean(axis=(1, 2))
    rbar = float(rbar_op.mean())
    x_diff = float(xbar_op.max() - xbar_op.min())
    part_means = y.mean(axis=(0, 1))
    rp = float(part_means.max() - part_means.min())

    k1, k2, k3 = C.K1[r], C.K2[o], C.K3[p]
    ev = rbar * k1
    av_sq = (x_diff * k2) ** 2 - ev ** 2 / (p * r)
    if av_sq < 0:
        warnings.append("AV under the square root is negative; AV is set to 0")
    av = float(np.sqrt(max(av_sq, 0.0)))
    grr = float(np.hypot(ev, av))
    pv = rp * k3
    tv = float(np.hypot(grr, pv))

    ucl_r = C.D4[r] * rbar
    out_of_control = [{"operator": ops[i], "part": parts[j], "range": float(ranges[i, j])}
                      for i in range(o) for j in range(p) if ranges[i, j] > ucl_r]
    if out_of_control:
        warnings.append(f"{len(out_of_control)} range(s) exceed UCL_R = D4 x R-bar; investigate before accepting")

    rows, metrics = grr_indicators({"EV": ev, "AV": av, "GRR": grr, "PV": pv, "TV": tv}, tol, k, C.NDC_FACTOR,
                                   warnings)
    resolution_metric(resolution, tol, metrics)
    metrics["ranges_out_of_control"] = len(out_of_control)
    return clean({
        "method": METHOD,
        "algorithm_version": VERSION,
        "model": "Average & Range: EV = R-bar*K1; AV = sqrt((Xdiff*K2)^2 - EV^2/(n*r)); PV = Rp*K3",
        "design": {"operators": ops, "parts": parts, "trials": trials, "tolerance": tol, "study_var_multiplier": k},
        "metrics": metrics,
        "tables": {"components": rows,
                   "operators": [{"operator": ops[i], "average": float(xbar_op[i]), "average_range": float(rbar_op[i])}
                                 for i in range(o)],
                   "out_of_control_ranges": out_of_control},
        "intermediate": {"r_bar": rbar, "x_diff": x_diff, "rp": rp, "k1": k1, "k2": k2, "k3": k3,
                         "ucl_r": ucl_r, "part_averages": part_means.tolist()},
        "charts": charts(y, ops, parts, C.D2, C.A2[r], C.D3[r], C.D4[r]),
        "warnings": warnings,
    })
