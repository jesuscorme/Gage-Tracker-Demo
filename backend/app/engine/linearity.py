"""Linearity study (AIAG MSA 4th ed., Chapter III Section B).

g reference parts across the operating range, each measured m times. Every individual
bias (x - reference) is regressed on the reference value: bias = a * reference + b.
The linearity is statistically acceptable when the "bias = 0" line lies entirely
inside the (1 - alpha) confidence bands of the fitted line, which is equivalent to
neither the slope nor the intercept being significantly different from zero over the
studied range. t tests of slope and intercept use df = g*m - 2.
"""

import math

import numpy as np
from scipy import stats

from app.engine.common import Checker, clean, label, natural, number

METHOD = "LINEARITY"
VERSION = "1.0.0"


def calculate(data: dict) -> dict:
    chk = Checker()
    obs, params = data.get("observations") or [], data.get("params") or {}
    alpha = number(params.get("alpha", 0.05))
    if alpha is None or not 0 < alpha < 1:
        chk.add("invalid_parameter", "alpha must be between 0 and 1", field="alpha")
        alpha = 0.05
    refs: dict[str, float] = {}
    rows: list[tuple[str, float, float]] = []
    seen = set()
    for i, o in enumerate(obs, start=1):
        part, ref, val = label(o.get("part")), number(o.get("reference")), number(o.get("value"))
        if part is None:
            chk.add("missing_label", "'part' is missing", row=i, field="part")
        if ref is None:
            chk.add("missing_reference", "reference value is missing or invalid", row=i, field="reference")
        if val is None:
            chk.add("missing_value" if o.get("value") in (None, "") else "invalid_value", "value is missing or invalid",
                    row=i, field="value")
        if part is None or ref is None or val is None:
            continue
        if refs.setdefault(part, ref) != ref:
            chk.add("inconsistent_reference", f"part '{part}' has more than one reference value", row=i)
        key = (part, str(o.get("trial")))
        if o.get("trial") not in (None, "") and key in seen:
            chk.add("duplicate_observation", f"duplicate trial {o.get('trial')} for part '{part}'", row=i)
        seen.add(key)
        rows.append((part, ref, val))
    if not obs:
        chk.add("no_data", "the study has no observations")
    elif len(set(refs.values())) < 2 and not chk.issues:
        chk.add("insufficient_levels", "at least 2 different reference values are required", field="reference")
    if rows and len(rows) < 3 and not chk.issues:
        chk.add("insufficient_data", "at least 3 measurements are required")
    chk.raise_if_any()

    warnings = []
    parts = sorted(refs, key=lambda p: (refs[p], natural(p)))
    counts = {p: sum(1 for r in rows if r[0] == p) for p in parts}
    if len(parts) < 5 or min(counts.values()) < 10:
        warnings.append("AIAG suggests at least 5 parts measured at least 10 times each for a linearity study")
    if len(set(counts.values())) > 1:
        warnings.append("Parts have different numbers of measurements")

    x = np.array([r[1] for r in rows])
    y = np.array([r[2] - r[1] for r in rows])
    n = len(x)
    xbar = float(x.mean())
    sxx = float(((x - xbar) ** 2).sum())
    a = float(((x - xbar) * (y - y.mean())).sum() / sxx)
    b = float(y.mean() - a * xbar)
    resid = y - (a * x + b)
    df = n - 2
    s = math.sqrt(float((resid ** 2).sum()) / df)
    ss_tot = float(((y - y.mean()) ** 2).sum())
    r2 = 1 - float((resid ** 2).sum()) / ss_tot if ss_tot > 0 else None
    tcrit = float(stats.t.ppf(1 - alpha / 2, df))
    se_a = s / math.sqrt(sxx)
    se_b = s * math.sqrt(1 / n + xbar ** 2 / sxx)
    t_a = abs(a) / se_a if se_a > 0 else None
    t_b = abs(b) / se_b if se_b > 0 else None
    p_a = float(2 * stats.t.sf(t_a, df)) if t_a is not None else None
    p_b = float(2 * stats.t.sf(t_b, df)) if t_b is not None else None

    def band(x0: float) -> tuple[float, float, float]:
        fit = b + a * x0
        half = tcrit * s * math.sqrt(1 / n + (x0 - xbar) ** 2 / sxx)
        return fit, fit - half, fit + half

    grid = sorted(set([float(v) for v in x]))
    bands = [{"reference": g, "fit": f, "lower": lo, "upper": hi} for g, (f, lo, hi) in ((g, band(g)) for g in grid)]
    zero_inside = all(r["lower"] <= 0 <= r["upper"] for r in bands)
    per_part = []
    for p in parts:
        biases = [r[2] - r[1] for r in rows if r[0] == p]
        per_part.append({"part": p, "reference": refs[p], "n": len(biases), "average_bias": float(np.mean(biases))})
    if s == 0:
        warnings.append("Residual variation is zero: t tests are undefined")
    metrics = {
        "slope": a, "intercept": b, "r_squared": r2, "s": s, "abs_slope": abs(a), "pct_linearity": 100.0 * abs(a),
        "slope_p_value": p_a, "intercept_p_value": p_b,
        "slope_significant": None if p_a is None else p_a < alpha,
        "intercept_significant": None if p_b is None else p_b < alpha,
        "zero_line_within_bands": zero_inside,
    }
    return clean({
        "method": METHOD, "algorithm_version": VERSION,
        "model": "Least squares regression of individual bias on reference value with (1 - alpha) confidence bands",
        "design": {"parts": parts, "alpha": alpha, "measurements": n},
        "metrics": metrics,
        "tables": {"per_part": per_part,
                   "regression": {"slope": a, "intercept": b, "se_slope": se_a, "se_intercept": se_b, "t_slope": t_a,
                                  "t_intercept": t_b, "df": df, "t_critical": tcrit, "r_squared": r2, "s": s}},
        "intermediate": {"x_bar": xbar, "sxx": sxx},
        "charts": {"points": [{"reference": float(xi), "bias": float(yi)} for xi, yi in zip(x, y)],
                   "bands": bands, "averages": per_part},
        "warnings": warnings,
    })
