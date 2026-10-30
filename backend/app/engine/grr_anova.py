"""Crossed Gage R&R, ANOVA method (two-way random effects model, balanced design).

Model: y_ijk = mu + P_i + O_j + (PO)_ij + e_ijk, with parts, operators and their
interaction as random effects. Variance components come from the expected mean squares
(Montgomery & Runger; AIAG MSA 4th ed., Chapter III Section B, ANOVA method).
Negative variance estimates are set to zero.

When the interaction is not significant (p > interaction_alpha, default 0.25) the
reduced model pools the interaction into the error term. ``interaction_mode`` forces
the full ("include") or reduced ("exclude") model instead.
"""

import numpy as np
from scipy import stats

from app.engine import constants as C
from app.engine.common import clean, grr_indicators, number, study_multiplier
from app.engine.crossed import charts, parse, resolution_metric

METHOD = "GRR_CROSSED_ANOVA"
VERSION = "1.0.0"


def anova_table(y: np.ndarray) -> dict:
    """Sums of squares of the balanced two-way design. y[operator, trial, part]."""
    o, r, p = y.shape
    gm = y.mean()
    op_m = y.mean(axis=(1, 2))
    part_m = y.mean(axis=(0, 1))
    cell = y.mean(axis=1)                                   # [op, part]
    ss_o = p * r * float(((op_m - gm) ** 2).sum())
    ss_p = o * r * float(((part_m - gm) ** 2).sum())
    ss_po = r * float(((cell - op_m[:, None] - part_m[None, :] + gm) ** 2).sum())
    ss_e = float(((y - cell[:, None, :]) ** 2).sum())
    ss_t = float(((y - gm) ** 2).sum())
    return {"o": o, "r": r, "p": p, "ss_o": ss_o, "ss_p": ss_p, "ss_po": ss_po, "ss_e": ss_e, "ss_t": ss_t,
            "df_o": o - 1, "df_p": p - 1, "df_po": (o - 1) * (p - 1), "df_e": o * p * (r - 1),
            "df_t": o * p * r - 1}


def _row(source, ss, df, ms, f=None, p=None):
    return {"source": source, "df": df, "ss": ss, "ms": ms, "f": f, "p": p}


def calculate(data: dict) -> dict:
    params = data.get("params") or {}
    chk, y, ops, parts, trials, tol, resolution = parse(data)
    k = study_multiplier(chk, params)
    alpha = number(params.get("interaction_alpha", 0.25))
    if alpha is None or not 0 < alpha < 1:
        chk.add("invalid_parameter", "interaction_alpha must be between 0 and 1", field="interaction_alpha")
    mode = params.get("interaction_mode", "auto")
    if mode not in ("auto", "include", "exclude"):
        chk.add("invalid_parameter", "interaction_mode must be auto, include or exclude", field="interaction_mode")
    chk.raise_if_any()

    t = anova_table(y)
    o, r, p = t["o"], t["r"], t["p"]
    warnings: list[str] = []
    ms_o, ms_p = t["ss_o"] / t["df_o"], t["ss_p"] / t["df_p"]
    ms_po, ms_e = t["ss_po"] / t["df_po"], t["ss_e"] / t["df_e"]
    if ms_e == 0:
        warnings.append("Repeatability mean square is zero (identical repeated readings): check the resolution")
    f_po = ms_po / ms_e if ms_e > 0 else None
    p_po = float(stats.f.sf(f_po, t["df_po"], t["df_e"])) if f_po is not None else None

    full = {"include": True, "exclude": False}.get(mode, p_po is not None and p_po <= alpha)
    if full:
        den = ms_po
        f_o, f_p = (ms_o / den, ms_p / den) if den > 0 else (None, None)
        p_o = float(stats.f.sf(f_o, t["df_o"], t["df_po"])) if f_o is not None else None
        p_p = float(stats.f.sf(f_p, t["df_p"], t["df_po"])) if f_p is not None else None
        table = [_row("Part", t["ss_p"], t["df_p"], ms_p, f_p, p_p),
                 _row("Operator", t["ss_o"], t["df_o"], ms_o, f_o, p_o),
                 _row("Part x Operator", t["ss_po"], t["df_po"], ms_po, f_po, p_po),
                 _row("Repeatability", t["ss_e"], t["df_e"], ms_e),
                 _row("Total", t["ss_t"], t["df_t"], None)]
        var_e = ms_e
        var_int = max((ms_po - ms_e) / r, 0.0)
        var_o = max((ms_o - ms_po) / (p * r), 0.0)
        var_p = max((ms_p - ms_po) / (o * r), 0.0)
        model = "Two-way random effects ANOVA with Part x Operator interaction"
    else:
        df_pool = t["df_po"] + t["df_e"]
        ms_pool = (t["ss_po"] + t["ss_e"]) / df_pool
        f_o, f_p = (ms_o / ms_pool, ms_p / ms_pool) if ms_pool > 0 else (None, None)
        p_o = float(stats.f.sf(f_o, t["df_o"], df_pool)) if f_o is not None else None
        p_p = float(stats.f.sf(f_p, t["df_p"], df_pool)) if f_p is not None else None
        table = [_row("Part", t["ss_p"], t["df_p"], ms_p, f_p, p_p),
                 _row("Operator", t["ss_o"], t["df_o"], ms_o, f_o, p_o),
                 _row("Repeatability", t["ss_po"] + t["ss_e"], df_pool, ms_pool),
                 _row("Total", t["ss_t"], t["df_t"], None)]
        var_e, var_int = ms_pool, 0.0
        var_o = max((ms_o - ms_pool) / (p * r), 0.0)
        var_p = max((ms_p - ms_pool) / (o * r), 0.0)
        model = "Two-way random effects ANOVA without interaction (interaction pooled into repeatability)"
    if (full and (ms_po - ms_e) < 0) or ms_o < (ms_po if full else ms_e):
        warnings.append("A negative variance component estimate was set to zero")

    ev, av, interaction = np.sqrt(var_e), np.sqrt(var_o), np.sqrt(var_int)
    reproducibility = float(np.sqrt(var_o + var_int))
    grr = float(np.sqrt(var_e + var_o + var_int))
    pv = float(np.sqrt(var_p))
    tv = float(np.sqrt(var_e + var_o + var_int + var_p))
    comps = {"EV": float(ev), "AV": float(av)}
    if full:
        comps["INT"] = float(interaction)
        comps["Reproducibility"] = reproducibility
    comps.update({"GRR": grr, "PV": pv, "TV": tv})
    rows, metrics = grr_indicators(comps, tol, k, C.NDC_FACTOR, warnings)
    resolution_metric(resolution, tol, metrics)
    metrics["interaction_p_value"] = p_po
    metrics["interaction_in_model"] = full
    metrics["operator_p_value"] = p_o

    rbar = float((y.max(axis=1) - y.min(axis=1)).mean())
    chart_consts = (C.A2[r], C.D3[r], C.D4[r]) if r in C.A2 else (None, 0.0, None)
    ch = charts(y, ops, parts, C.D2, *(c if c is not None else 0.0 for c in chart_consts))
    if r not in C.A2:
        ch["range_chart"]["ucl"] = ch["average_chart"]["ucl"] = ch["average_chart"]["lcl"] = None
    return clean({
        "method": METHOD,
        "algorithm_version": VERSION,
        "model": model,
        "design": {"operators": ops, "parts": parts, "trials": trials, "tolerance": tol, "study_var_multiplier": k,
                   "interaction_alpha": alpha, "interaction_mode": mode},
        "metrics": metrics,
        "tables": {"anova": table, "components": rows},
        "intermediate": {"anova_full": {**t, "ms_o": ms_o, "ms_p": ms_p, "ms_po": ms_po, "ms_e": ms_e,
                                        "f_interaction": f_po, "p_interaction": p_po},
                         "variance_components": {"repeatability": var_e, "operator": var_o,
                                                 "interaction": var_int, "part": var_p},
                         "r_bar": rbar},
        "charts": ch,
        "warnings": warnings,
    })
