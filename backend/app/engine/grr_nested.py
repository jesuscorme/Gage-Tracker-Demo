"""Nested Gage R&R (parts nested within operators), ANOVA method.

Used when a part can only be measured by one operator (destructive tests, parts that
cannot travel). Model: y_ijk = mu + O_i + P(O)_j(i) + e_k(ij), random effects.

Expected mean squares (balanced):  E[MS_E] = s2_e;  E[MS_P(O)] = s2_e + r*s2_p;
E[MS_O] = s2_e + r*s2_p + p*r*s2_o, with p parts per operator and r trials. The
operator x part interaction cannot be estimated in this design (it is confounded with
part-to-part variation), so the crossed formulas are deliberately not reused.
"""

import numpy as np
from scipy import stats

from app.engine import constants as C
from app.engine.common import (Checker, balanced_cells, check_count, clean, grr_indicators, natural, number,
                               study_multiplier, tolerance_of)

METHOD = "GRR_NESTED_ANOVA"
VERSION = "1.0.0"
KEYS = ("operator", "part", "trial")


def parse(data: dict):
    chk = Checker()
    design, obs = data.get("design") or {}, data.get("observations") or []
    if not obs:
        chk.add("no_data", "the study has no observations")
        chk.raise_if_any()
    cells = balanced_cells(chk, obs, KEYS)
    owner: dict[str, str] = {}
    for (op, part, _t) in cells:
        if owner.setdefault(part, op) != op:
            chk.add("part_not_nested", f"part '{part}' is measured by more than one operator; "
                                       "this is a crossed design, not a nested one")
    ops = sorted({c[0] for c in cells}, key=natural)
    parts_of = {o: sorted({c[1] for c in cells if c[0] == o}, key=natural) for o in ops}
    trials_of = {(o, p): sorted({c[2] for c in cells if c[0] == o and c[1] == p}) for o in ops for p in parts_of[o]}
    n_parts = {len(v) for v in parts_of.values()}
    n_trials = {len(v) for v in trials_of.values()}
    if len(n_parts) > 1:
        chk.add("unbalanced_design", "every operator must measure the same number of parts "
                                     f"(found {sorted(n_parts)})")
    if len(n_trials) > 1:
        chk.add("unbalanced_design", f"every part must have the same number of trials (found {sorted(n_trials)})")
    p = min(n_parts) if n_parts else 0
    r = min(n_trials) if n_trials else 0
    check_count(chk, design, "operators", len(ops), 2)
    check_count(chk, design, "parts_per_operator", p, 2)
    check_count(chk, design, "trials", r, 2)
    tol = tolerance_of(chk, design)
    chk.raise_if_any()
    y = np.array([[[cells[(o, part, t)] for t in trials_of[(o, part)]] for part in parts_of[o]] for o in ops],
                 dtype=float)   # [op, part-within-op, trial]
    return chk, y, ops, parts_of, tol, number(design.get("resolution"))


def anova_table(y: np.ndarray) -> dict:
    o, p, r = y.shape
    gm = y.mean()
    op_m = y.mean(axis=(1, 2))
    cell = y.mean(axis=2)                                   # [op, part]
    ss_o = p * r * float(((op_m - gm) ** 2).sum())
    ss_po = r * float(((cell - op_m[:, None]) ** 2).sum())
    ss_e = float(((y - cell[:, :, None]) ** 2).sum())
    ss_t = float(((y - gm) ** 2).sum())
    return {"o": o, "p": p, "r": r, "ss_o": ss_o, "ss_p_in_o": ss_po, "ss_e": ss_e, "ss_t": ss_t,
            "df_o": o - 1, "df_p_in_o": o * (p - 1), "df_e": o * p * (r - 1), "df_t": o * p * r - 1}


def calculate(data: dict) -> dict:
    params = data.get("params") or {}
    chk, y, ops, parts_of, tol, resolution = parse(data)
    k = study_multiplier(chk, params)
    chk.raise_if_any()
    t = anova_table(y)
    o, p, r = t["o"], t["p"], t["r"]
    warnings: list[str] = []
    ms_o = t["ss_o"] / t["df_o"]
    ms_po = t["ss_p_in_o"] / t["df_p_in_o"]
    ms_e = t["ss_e"] / t["df_e"]
    f_o = ms_o / ms_po if ms_po > 0 else None
    f_po = ms_po / ms_e if ms_e > 0 else None
    p_o = float(stats.f.sf(f_o, t["df_o"], t["df_p_in_o"])) if f_o is not None else None
    p_po = float(stats.f.sf(f_po, t["df_p_in_o"], t["df_e"])) if f_po is not None else None

    var_e = ms_e
    var_p = (ms_po - ms_e) / r
    var_o = (ms_o - ms_po) / (p * r)
    if var_p < 0 or var_o < 0:
        warnings.append("A negative variance component estimate was set to zero")
    var_p, var_o = max(var_p, 0.0), max(var_o, 0.0)
    if ms_e == 0:
        warnings.append("Repeatability mean square is zero (identical repeated readings): check the resolution")

    grr = float(np.sqrt(var_e + var_o))
    pv = float(np.sqrt(var_p))
    tv = float(np.sqrt(var_e + var_o + var_p))
    rows, metrics = grr_indicators({"EV": float(np.sqrt(var_e)), "AV": float(np.sqrt(var_o)), "GRR": grr,
                                    "PV": pv, "TV": tv}, tol, k, C.NDC_FACTOR, warnings)
    metrics["resolution_pct_tolerance"] = (100.0 * resolution / tol) if resolution and tol else None
    metrics["operator_p_value"] = p_o
    table = [
        {"source": "Operator", "df": t["df_o"], "ss": t["ss_o"], "ms": ms_o, "f": f_o, "p": p_o},
        {"source": "Part (Operator)", "df": t["df_p_in_o"], "ss": t["ss_p_in_o"], "ms": ms_po, "f": f_po, "p": p_po},
        {"source": "Repeatability", "df": t["df_e"], "ss": t["ss_e"], "ms": ms_e, "f": None, "p": None},
        {"source": "Total", "df": t["df_t"], "ss": t["ss_t"], "ms": None, "f": None, "p": None},
    ]
    cell = y.mean(axis=2)
    return clean({
        "method": METHOD,
        "algorithm_version": VERSION,
        "model": "Nested random effects ANOVA: Operator, Part(Operator), Repeatability",
        "design": {"operators": ops, "parts_by_operator": parts_of, "parts_per_operator": p, "trials": r,
                   "tolerance": tol, "study_var_multiplier": k},
        "metrics": metrics,
        "tables": {"anova": table, "components": rows},
        "intermediate": {"anova_full": t | {"ms_o": ms_o, "ms_p_in_o": ms_po, "ms_e": ms_e},
                         "variance_components": {"repeatability": var_e, "operator": var_o, "part_in_operator": var_p}},
        "charts": {
            "by_operator": {"operators": ops, "values": [y[i].ravel().tolist() for i in range(o)]},
            "part_means": {"operators": ops, "parts": [parts_of[op] for op in ops], "values": cell.tolist()},
            "ranges": {"operators": ops, "values": (y.max(axis=2) - y.min(axis=2)).tolist()},
        },
        "warnings": warnings,
    })
