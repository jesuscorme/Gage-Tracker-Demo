"""Bias study, independent sample method (AIAG MSA 4th ed., Chapter III Section B).

n repeated measurements of one reference part. bias_i = x_i - reference; the average
bias is tested against zero with a two-sided t test (df = n - 1) using the repeatability
standard deviation s and sigma_b = s / sqrt(n). The bias is statistically acceptable at
level alpha when zero lies inside the (1 - alpha) confidence interval of the bias.
"""

import math

import numpy as np
from scipy import stats

from app.engine.common import Checker, clean, design_number, number, tolerance_of

METHOD = "BIAS"
VERSION = "1.0.0"


def values_of(chk: Checker, obs: list[dict]) -> list[float]:
    out = []
    for i, o in enumerate(obs, start=1):
        v = number(o.get("value"))
        if v is None:
            chk.add("missing_value" if o.get("value") in (None, "") else "invalid_value", "value is missing or invalid",
                    row=i, field="value")
        else:
            out.append(v)
    seqs = [o.get("trial") for o in obs if o.get("trial") not in (None, "")]
    if len(seqs) != len(set(map(str, seqs))):
        chk.add("duplicate_observation", "repeated trial numbers")
    return out


def t_interval(values: np.ndarray, reference: float, alpha: float) -> dict:
    n = len(values)
    bias = values - reference
    avg = float(bias.mean())
    s = float(values.std(ddof=1))
    sb = s / math.sqrt(n)
    df = n - 1
    tcrit = float(stats.t.ppf(1 - alpha / 2, df))
    t = avg / sb if sb > 0 else None
    p = float(2 * stats.t.sf(abs(t), df)) if t is not None else None
    return {"n": n, "average": float(values.mean()), "bias": avg, "s": s, "sigma_b": sb, "df": df, "t": t,
            "t_critical": tcrit, "p_value": p, "ci_low": avg - tcrit * sb, "ci_high": avg + tcrit * sb}


def histogram(values: np.ndarray, bins: int = 10) -> dict:
    if values.min() == values.max():
        return {"edges": [float(values.min()), float(values.max())], "counts": [len(values)]}
    counts, edges = np.histogram(values, bins=min(bins, max(3, int(math.sqrt(len(values))))))
    return {"edges": edges.tolist(), "counts": counts.tolist()}


def calculate(data: dict) -> dict:
    chk = Checker()
    design, obs, params = data.get("design") or {}, data.get("observations") or [], data.get("params") or {}
    reference = design_number(chk, design, "reference", required=True)
    tol = tolerance_of(chk, design)
    alpha = number(params.get("alpha", 0.05))
    if alpha is None or not 0 < alpha < 1:
        chk.add("invalid_parameter", "alpha must be between 0 and 1", field="alpha")
    vals = values_of(chk, obs)
    if len(vals) < 2 and not any(i.code in ("missing_value", "invalid_value") for i in chk.issues):
        chk.add("insufficient_data", "at least 2 measurements are required")
    chk.raise_if_any()
    x = np.array(vals, dtype=float)
    warnings = []
    if len(x) < 10:
        warnings.append("At least 10 measurements are recommended for a bias study")
    r = t_interval(x, reference, alpha)
    if r["s"] == 0:
        warnings.append("All readings are identical: repeatability is zero and the t test is undefined")
    significant = None if r["t"] is None else not (r["ci_low"] <= 0 <= r["ci_high"])
    metrics = {
        "bias": r["bias"], "abs_bias": abs(r["bias"]), "repeatability_sd": r["s"], "t_statistic": r["t"],
        "p_value": r["p_value"], "bias_significant": significant,
        "pct_bias_tolerance": 100.0 * abs(r["bias"]) / tol if tol else None,
    }
    return clean({
        "method": METHOD, "algorithm_version": VERSION,
        "model": "Independent sample bias: two-sided t test of average bias = 0, df = n - 1",
        "design": {"reference": reference, "tolerance": tol, "alpha": alpha},
        "metrics": metrics,
        "tables": {"summary": r},
        "intermediate": {"biases": (x - reference).tolist()},
        "charts": {"histogram": histogram(x), "values": x.tolist(), "reference": reference,
                   "ci": [r["ci_low"] + reference, r["ci_high"] + reference]},
        "warnings": warnings,
    })
