"""Stability study: control chart of a reference part measured over time.

Subgroup size n = 1 uses an Individuals / Moving Range chart; 2 <= n <= 10 an X-bar / R
chart. Constants: AIAG SPC Manual 2nd ed., Appendix E (pp. 181-182). Special-cause
criteria: AIAG SPC Manual 2nd ed., Table II.1 "Summary of Typical Special Cause
Criteria" (p. 75); each criterion is enabled and parameterised by configuration, as the
manual leaves the selection to the user. Sigma of the plotted statistic = (UCL - CL)/3.
"""

import numpy as np

from app.engine import constants as C
from app.engine.common import Checker, clean, number, positive_int

METHOD = "STABILITY"
VERSION = "1.0.0"

# Criterion number (Table II.1) -> default parameters.
DEFAULT_RULES = {
    "1": {"enabled": True},                    # 1 point beyond 3 sigma
    "2": {"enabled": True, "run": 7},          # run on same side of the centerline
    "3": {"enabled": True, "run": 6},          # run all increasing or all decreasing
    "4": {"enabled": False, "run": 14},        # alternating up and down
    "5": {"enabled": False},                   # 2 of 3 beyond 2 sigma, same side
    "6": {"enabled": False},                   # 4 of 5 beyond 1 sigma, same side
    "7": {"enabled": False, "run": 15},        # within 1 sigma
    "8": {"enabled": False, "run": 8},         # beyond 1 sigma, either side
}


def rule_config(chk: Checker, raw: dict | None) -> dict:
    cfg = {k: dict(v) for k, v in DEFAULT_RULES.items()}
    for key, val in (raw or {}).items():
        if key not in cfg or not isinstance(val, dict):
            chk.add("invalid_parameter", f"unknown special-cause criterion '{key}'", field="rules")
            continue
        if "enabled" in val:
            cfg[key]["enabled"] = bool(val["enabled"])
        if "run" in val:
            run = positive_int(val["run"])
            if "run" not in cfg[key] or run is None or run < 2:
                chk.add("invalid_parameter", f"criterion {key}: run must be an integer >= 2", field="rules")
            else:
                cfg[key]["run"] = run
    return cfg


def special_causes(x: list[float], cl: float, sigma: float, cfg: dict) -> list[dict]:
    """Return {rule, index} for the point that completes each pattern."""
    out = []
    n = len(x)
    if sigma <= 0:
        return out
    z = [(v - cl) / sigma for v in x]

    def add(rule, i):
        out.append({"rule": rule, "index": i})

    if cfg["1"]["enabled"]:
        for i, v in enumerate(z):
            if abs(v) > 3:
                add("1", i)
    if cfg["2"]["enabled"]:
        run = cfg["2"]["run"]
        for i in range(run - 1, n):
            w = z[i - run + 1:i + 1]
            if all(v > 0 for v in w) or all(v < 0 for v in w):
                add("2", i)
    if cfg["3"]["enabled"]:
        run = cfg["3"]["run"]
        for i in range(run - 1, n):
            w = x[i - run + 1:i + 1]
            d = [b - a for a, b in zip(w, w[1:])]
            if all(v > 0 for v in d) or all(v < 0 for v in d):
                add("3", i)
    if cfg["4"]["enabled"]:
        run = cfg["4"]["run"]
        for i in range(run - 1, n):
            w = x[i - run + 1:i + 1]
            d = [b - a for a, b in zip(w, w[1:])]
            if all(d[j] != 0 and (d[j] > 0) != (d[j + 1] > 0) for j in range(len(d) - 1)) and d[-1] != 0:
                add("4", i)
    if cfg["5"]["enabled"]:
        for i in range(2, n):
            w = z[i - 2:i + 1]
            if sum(v > 2 for v in w) >= 2 or sum(v < -2 for v in w) >= 2:
                add("5", i)
    if cfg["6"]["enabled"]:
        for i in range(4, n):
            w = z[i - 4:i + 1]
            if sum(v > 1 for v in w) >= 4 or sum(v < -1 for v in w) >= 4:
                add("6", i)
    if cfg["7"]["enabled"]:
        run = cfg["7"]["run"]
        for i in range(run - 1, n):
            if all(abs(v) < 1 for v in z[i - run + 1:i + 1]):
                add("7", i)
    if cfg["8"]["enabled"]:
        run = cfg["8"]["run"]
        for i in range(run - 1, n):
            if all(abs(v) > 1 for v in z[i - run + 1:i + 1]):
                add("8", i)
    return out


def calculate(data: dict) -> dict:
    chk = Checker()
    design, obs, params = data.get("design") or {}, data.get("observations") or [], data.get("params") or {}
    n = positive_int(design.get("subgroup_size", 1))
    if n is None or n > 10:
        chk.add("invalid_parameter", "subgroup_size must be an integer between 1 and 10", field="subgroup_size")
        n = 1
    reference = number(design.get("reference"))
    cfg = rule_config(chk, params.get("rules"))
    groups: dict[int, list[tuple[str, float]]] = {}
    for i, o in enumerate(obs, start=1):
        sg, val = positive_int(o.get("subgroup")), number(o.get("value"))
        if sg is None:
            chk.add("missing_label", "subgroup must be a positive integer (chronological order)", row=i,
                    field="subgroup")
        if val is None:
            chk.add("missing_value" if o.get("value") in (None, "") else "invalid_value", "value is missing or invalid",
                    row=i, field="value")
        if sg is not None and val is not None:
            groups.setdefault(sg, []).append((str(o.get("measured_at") or ""), val))
    if not obs:
        chk.add("no_data", "the study has no observations")
    for sg, vals in sorted(groups.items()):
        if len(vals) != n:
            chk.add("incomplete_subgroup", f"subgroup {sg} has {len(vals)} readings, expected {n}")
    if len(groups) < 2 + (1 if n == 1 else 0) and not chk.issues:
        chk.add("insufficient_data", "not enough subgroups to compute control limits")
    chk.raise_if_any()

    order = sorted(groups)
    warnings = []
    if len(order) < 20:
        warnings.append("Fewer than 20 subgroups: control limits are preliminary")
    stamps = [max(t for t, _ in groups[g]) or None for g in order]
    if n == 1:
        x = [groups[g][0][1] for g in order]
        mr = [abs(b - a) for a, b in zip(x, x[1:])]
        center = float(np.mean(x))
        mr_bar = float(np.mean(mr))
        ucl, lcl = center + C.E2 * mr_bar, center - C.E2 * mr_bar
        sigma = mr_bar / C.D2[2]
        disp = {"kind": "MR", "values": [None] + mr, "center": mr_bar, "ucl": C.D4[2] * mr_bar, "lcl": 0.0}
        chart = "I-MR"
    else:
        sub = [[v for _, v in groups[g]] for g in order]
        x = [float(np.mean(s)) for s in sub]
        rr = [max(s) - min(s) for s in sub]
        center = float(np.mean(x))
        r_bar = float(np.mean(rr))
        ucl, lcl = center + C.A2[n] * r_bar, center - C.A2[n] * r_bar
        sigma = r_bar / C.D2[n]
        disp = {"kind": "R", "values": rr, "center": r_bar, "ucl": C.D4[n] * r_bar, "lcl": C.D3[n] * r_bar}
        chart = "Xbar-R"
    violations = special_causes(x, center, (ucl - center) / 3, cfg)
    disp_out = [i for i, v in enumerate(disp["values"]) if v is not None and v > disp["ucl"]]
    if sigma == 0:
        warnings.append("No variation between readings: control limits collapse; check the resolution")
    metrics = {
        "stable": not violations and not disp_out,
        "violations": len(violations),
        "dispersion_out_of_control": len(disp_out),
        "process_mean": center,
        "sigma": sigma,
        "bias": center - reference if reference is not None else None,
    }
    return clean({
        "method": METHOD, "algorithm_version": VERSION,
        "model": f"{chart} control chart with AIAG SPC Table II.1 special-cause criteria",
        "design": {"subgroup_size": n, "reference": reference, "rules": cfg, "subgroups": len(order)},
        "metrics": metrics,
        "tables": {"violations": [v | {"subgroup": order[v["index"]]} for v in violations],
                   "dispersion_out_of_control": [{"subgroup": order[i]} for i in disp_out]},
        "intermediate": {"sigma_estimate": sigma},
        "charts": {"location": {"kind": "I" if n == 1 else "Xbar", "subgroups": order, "timestamps": stamps,
                                "values": x, "center": center, "ucl": ucl, "lcl": lcl, "reference": reference,
                                "violations": violations},
                   "dispersion": disp | {"subgroups": order}},
        "warnings": warnings,
    })
