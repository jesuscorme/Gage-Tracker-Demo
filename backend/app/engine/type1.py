"""Type 1 gage study (capability of the measurement system on one reference part).

Indices as defined in Robert Bosch GmbH, Booklet No. 10 "Capability of Measurement and
Test Processes" (also adopted by VDA Volume 5), with K (percentage of the tolerance,
default 20) and L (number of standard deviations, default 6) as configurable method
parameters:

    Cg  = (K/100 * T) / (L * s)
    Cgk = (K/200 * T - |x_bar - x_m|) / (L/2 * s)

where T is the characteristic tolerance, x_m the reference value and s the standard
deviation of the repeated readings. The bias is also tested against zero (t test).
"""

import numpy as np

from app.engine.bias import histogram, t_interval, values_of
from app.engine.common import Checker, clean, design_number, number, tolerance_of

METHOD = "TYPE1"
VERSION = "1.0.0"


def calculate(data: dict) -> dict:
    chk = Checker()
    design, obs, params = data.get("design") or {}, data.get("observations") or [], data.get("params") or {}
    reference = design_number(chk, design, "reference", required=True)
    tol = tolerance_of(chk, design)
    if tol is None and not any(i.field in ("tolerance", "usl") for i in chk.issues):
        chk.add("missing_parameter", "the tolerance (or lsl and usl) is required for a Type 1 study", field="tolerance")
    k_pct = number(params.get("k_percent", 20))
    big_l = number(params.get("l_sigma", 6))
    alpha = number(params.get("alpha", 0.05))
    if k_pct is None or not 0 < k_pct <= 100:
        chk.add("invalid_parameter", "k_percent must be in (0, 100]", field="k_percent")
    if big_l is None or big_l <= 0:
        chk.add("invalid_parameter", "l_sigma must be positive", field="l_sigma")
    if alpha is None or not 0 < alpha < 1:
        chk.add("invalid_parameter", "alpha must be between 0 and 1", field="alpha")
    vals = values_of(chk, obs)
    if len(vals) < 2 and not any(i.code in ("missing_value", "invalid_value") for i in chk.issues):
        chk.add("insufficient_data", "at least 2 measurements are required")
    chk.raise_if_any()

    x = np.array(vals, dtype=float)
    warnings = []
    if len(x) < 25:
        warnings.append("At least 25 readings are recommended (50 preferred)")
    r = t_interval(x, reference, alpha)
    s = r["s"]
    if s == 0:
        warnings.append("All readings are identical (s = 0): Cg and Cgk are undefined; check the resolution")
        cg = cgk = None
    else:
        cg = (k_pct / 100 * tol) / (big_l * s)
        cgk = (k_pct / 200 * tol - abs(r["bias"])) / (big_l / 2 * s)
    resolution = number(design.get("resolution"))
    metrics = {
        "cg": cg, "cgk": cgk, "bias": r["bias"], "abs_bias": abs(r["bias"]), "repeatability_sd": s,
        "bias_p_value": r["p_value"],
        "bias_significant": None if r["t"] is None else not (r["ci_low"] <= 0 <= r["ci_high"]),
        "resolution_pct_tolerance": 100.0 * resolution / tol if resolution else None,
    }
    half = k_pct / 200 * tol
    return clean({
        "method": METHOD, "algorithm_version": VERSION,
        "model": "Type 1 study: Cg = (K/100*T)/(L*s), Cgk = (K/200*T - |bias|)/(L/2*s)",
        "design": {"reference": reference, "tolerance": tol, "k_percent": k_pct, "l_sigma": big_l, "alpha": alpha},
        "metrics": metrics,
        "tables": {"summary": r | {"cg": cg, "cgk": cgk}},
        "intermediate": {"k_band_half_width": half},
        "charts": {"run": {"values": x.tolist(), "reference": reference,
                           "lower": reference - half, "upper": reference + half,
                           "mean": r["average"]},
                   "histogram": histogram(x)},
        "warnings": warnings,
    })
