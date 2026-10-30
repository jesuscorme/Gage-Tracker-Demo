"""Contracts shared by every method: input parsing, design issues and result helpers.

Input contract (JSON-compatible, so a stored run can be replayed byte for byte)::

    {"design": {...}, "observations": [{...}, ...], "params": {...}}

Output contract::

    {"method", "algorithm_version", "model", "metrics": {name: number|bool|None},
     "tables": {...}, "charts": {...}, "intermediate": {...}, "warnings": [str]}

Design problems never produce numbers: they raise :class:`DesignError` with every issue
found, so the user can fix the data in one pass.
"""

import math
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any


@dataclass
class Issue:
    code: str
    message: str
    row: int | None = None
    field: str | None = None

    def as_dict(self) -> dict:
        return {k: v for k, v in self.__dict__.items() if v is not None}


class DesignError(Exception):
    def __init__(self, issues: list[Issue]):
        super().__init__("; ".join(i.message for i in issues))
        self.issues = issues


@dataclass
class Checker:
    issues: list[Issue] = field(default_factory=list)

    def add(self, code: str, message: str, row: int | None = None, field: str | None = None) -> None:
        self.issues.append(Issue(code, message, row, field))

    def raise_if_any(self) -> None:
        if self.issues:
            raise DesignError(self.issues)


def number(value: Any) -> float | None:
    """Finite float or None (booleans are not numbers)."""
    if isinstance(value, bool) or value is None:
        return None
    try:
        f = float(value)
    except (TypeError, ValueError):
        return None
    return f if math.isfinite(f) else None


def positive_int(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    try:
        i = int(value)
    except (TypeError, ValueError):
        return None
    return i if i >= 1 and float(value) == i else None


def label(value: Any) -> str | None:
    if value is None:
        return None
    s = str(value).strip()
    return s or None


def design_number(chk: Checker, design: dict, name: str, *, required: bool = False, positive: bool = False):
    raw = design.get(name)
    if raw is None or raw == "":
        if required:
            chk.add("missing_parameter", f"'{name}' is required", field=name)
        return None
    v = number(raw)
    if v is None or (positive and v <= 0):
        chk.add("invalid_parameter", f"'{name}' must be a {'positive ' if positive else ''}number", field=name)
        return None
    return v


def tolerance_of(chk: Checker, design: dict) -> float | None:
    """Tolerance from ``tolerance`` or from ``lsl``/``usl`` (optional unless the method needs it)."""
    tol = design_number(chk, design, "tolerance", positive=True)
    lsl, usl = number(design.get("lsl")), number(design.get("usl"))
    if tol is None and lsl is not None and usl is not None:
        if usl <= lsl:
            chk.add("invalid_parameter", "usl must be greater than lsl", field="usl")
        else:
            tol = usl - lsl
    return tol


def balanced_cells(chk: Checker, observations: list[dict], keys: tuple[str, ...], *, need_value: bool = True,
                   value_key: str = "value", categorical: bool = False) -> dict[tuple, Any]:
    """Map (k1, k2, ...) -> value. Reports missing labels, bad values and duplicates per row."""
    cells: dict[tuple, Any] = {}
    for i, obs in enumerate(observations, start=1):
        ok = True
        key = []
        for k in keys:
            if k == "trial":
                v = positive_int(obs.get(k))
                if v is None:
                    chk.add("invalid_trial", "trial must be a positive integer", row=i, field=k)
                    ok = False
            else:
                v = label(obs.get(k))
                if v is None:
                    chk.add("missing_label", f"'{k}' is missing", row=i, field=k)
                    ok = False
            key.append(v)
        raw = obs.get(value_key)
        if categorical:
            val = label(raw)
        else:
            val = number(raw)
        if need_value and val is None:
            chk.add("missing_value" if raw in (None, "") else "invalid_value",
                    "value is missing" if raw in (None, "") else f"value '{raw}' is not valid", row=i, field=value_key)
            ok = False
        if not ok:
            continue
        t = tuple(key)
        if t in cells:
            chk.add("duplicate_observation", f"duplicate observation for {dict(zip(keys, t))}", row=i)
            continue
        cells[t] = val
    return cells


def require_full_factorial(chk: Checker, cells: dict[tuple, Any], keys: tuple[str, ...]) -> list[list[str]]:
    """Every combination of the observed levels must be present exactly once."""
    levels = [sorted({c[i] for c in cells}, key=natural) for i in range(len(keys))]
    missing = []

    def walk(prefix):
        if len(prefix) == len(levels):
            if tuple(prefix) not in cells:
                missing.append(dict(zip(keys, prefix)))
            return
        for lv in levels[len(prefix)]:
            walk(prefix + [lv])

    if cells:
        walk([])
    for m in missing[:20]:
        chk.add("missing_observation", f"missing observation for {m}")
    if len(missing) > 20:
        chk.add("missing_observation", f"... and {len(missing) - 20} more missing observations")
    return levels


def check_count(chk: Checker, design: dict, name: str, actual: int, minimum: int, maximum: int | None = None) -> None:
    declared = design.get(name)
    if declared not in (None, ""):
        d = positive_int(declared)
        if d is None:
            chk.add("invalid_parameter", f"'{name}' must be a positive integer", field=name)
        elif d != actual:
            chk.add("design_mismatch", f"design declares {d} {name} but the data contains {actual}", field=name)
    if actual < minimum:
        chk.add("insufficient_levels", f"at least {minimum} {name} are required (found {actual})", field=name)
    if maximum is not None and actual > maximum:
        chk.add("too_many_levels", f"at most {maximum} {name} are supported by this method (found {actual})",
                field=name)


def natural(s: str):
    """Sort '2' before '10' when labels are numeric."""
    return (0, float(s), s) if number(s) is not None else (1, 0.0, s)


def safe_div(a: float, b: float) -> float | None:
    return None if b == 0 else a / b


def pct(a: float | None, b: float | None) -> float | None:
    if a is None or b is None or b == 0:
        return None
    return 100.0 * a / b


def clean(value: Any) -> Any:
    """Recursively replace NaN/inf with None and numpy scalars with Python floats."""
    if isinstance(value, dict):
        return {k: clean(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [clean(v) for v in value]
    if isinstance(value, bool) or value is None or isinstance(value, str):
        return value
    if hasattr(value, "item"):
        value = value.item()
    if isinstance(value, float):
        return value if math.isfinite(value) else None
    return value


def group(items, key):
    out = defaultdict(list)
    for it in items:
        out[key(it)].append(it)
    return out


def study_multiplier(chk: Checker, params: dict) -> float:
    k = params.get("study_var_multiplier", 6)
    v = number(k)
    if v not in (6.0, 5.15):
        chk.add("invalid_parameter", "study_var_multiplier must be 6 or 5.15", field="study_var_multiplier")
        return 6.0
    return v


def grr_indicators(components: dict[str, float], tolerance: float | None, k: float,
                   ndc_factor: float, warnings: list[str]) -> tuple[list[dict], dict]:
    """Common output for variable GRR methods.

    ``components`` holds standard deviations for EV, AV, INT (optional), GRR, PV and TV.
    %Contribution uses variances, %Study Variation and %Tolerance use standard deviations.
    """
    tv = components["TV"]
    rows = []
    for name, sd in components.items():
        rows.append({
            "source": name,
            "sd": sd,
            "variance": sd * sd,
            "study_var": k * sd,
            "pct_contribution": pct(sd * sd, tv * tv),
            "pct_study_var": pct(sd, tv),
            "pct_tolerance": pct(k * sd, tolerance) if tolerance else None,
        })
    grr, pv = components["GRR"], components["PV"]
    if grr == 0:
        warnings.append("GRR is zero (no measurement variation detected): ndc is undefined; check the resolution")
        ndc = None
    else:
        ndc = math.floor(ndc_factor * pv / grr)
    by = {r["source"]: r for r in rows}
    metrics = {
        "ev": components["EV"], "av": components["AV"], "grr": grr, "pv": pv, "tv": tv,
        "pct_sv_ev": by["EV"]["pct_study_var"], "pct_sv_av": by["AV"]["pct_study_var"],
        "pct_sv_grr": by["GRR"]["pct_study_var"], "pct_sv_pv": by["PV"]["pct_study_var"],
        "pct_contribution_grr": by["GRR"]["pct_contribution"],
        "pct_tolerance_grr": by["GRR"]["pct_tolerance"],
        "ndc": ndc,
    }
    if tv == 0:
        warnings.append("Total variation is zero: percentages are undefined")
    return rows, metrics
