"""Attribute Agreement Analysis (nominal categories).

Only categorical statistics are used — no continuous-variable formulas:

* percent agreement (within appraiser, appraiser vs reference, between appraisers,
  all appraisers vs reference) with exact Clopper-Pearson confidence intervals;
* Cohen's kappa for pairs of appraisers and for each appraiser vs the reference, from
  the cross-tabulation of paired classifications (AIAG MSA 4th ed., Chapter III
  Section C, hypothesis test / cross-tab approach);
* Fleiss' kappa for agreement among several ratings of the same part (within
  appraiser: trials as raters; between appraisers: every rating of the part);
* effectiveness, miss rate and false alarm rate for a binary accept/reject decision
  (AIAG MSA 4th ed., Chapter III Section C), when both categories are declared.
"""

from collections import Counter

from scipy import stats

from app.engine.common import Checker, balanced_cells, check_count, clean, label, natural, number, \
    require_full_factorial

METHOD = "ATTRIBUTE_AGREEMENT"
VERSION = "1.0.0"
KEYS = ("operator", "part", "trial")


def clopper_pearson(x: int, n: int, alpha: float) -> tuple[float | None, float | None]:
    if n == 0:
        return None, None
    lo = 0.0 if x == 0 else float(stats.beta.ppf(alpha / 2, x, n - x + 1))
    hi = 1.0 if x == n else float(stats.beta.ppf(1 - alpha / 2, x + 1, n - x))
    return 100 * lo, 100 * hi


def agreement(x: int, n: int, alpha: float) -> dict:
    lo, hi = clopper_pearson(x, n, alpha)
    return {"inspected": n, "matched": x, "pct": 100.0 * x / n if n else None, "ci_low": lo, "ci_high": hi}


def cohen_kappa(pairs: list[tuple[str, str]], categories: list[str]) -> tuple[float | None, list[list[int]]]:
    """Cohen's kappa and its contingency table (rows: first rater, columns: second)."""
    idx = {c: i for i, c in enumerate(categories)}
    m = [[0] * len(categories) for _ in categories]
    for a, b in pairs:
        m[idx[a]][idx[b]] += 1
    n = len(pairs)
    if n == 0:
        return None, m
    po = sum(m[i][i] for i in range(len(categories))) / n
    pe = sum(sum(m[i]) * sum(row[i] for row in m) for i in range(len(categories))) / (n * n)
    return (None if pe == 1 else (po - pe) / (1 - pe)), m


def fleiss_kappa(counts: list[list[int]]) -> float | None:
    """Fleiss' kappa from a subjects x categories count matrix (same raters per subject)."""
    if not counts:
        return None
    n = sum(counts[0])
    if n < 2 or any(sum(r) != n for r in counts):
        return None
    big_n = len(counts)
    k = len(counts[0])
    p_j = [sum(r[j] for r in counts) / (big_n * n) for j in range(k)]
    p_i = [(sum(c * c for c in r) - n) / (n * (n - 1)) for r in counts]
    p_bar = sum(p_i) / big_n
    p_e = sum(p * p for p in p_j)
    return None if p_e == 1 else (p_bar - p_e) / (1 - p_e)


def calculate(data: dict) -> dict:
    chk = Checker()
    design, obs, params = data.get("design") or {}, data.get("observations") or [], data.get("params") or {}
    if not obs:
        chk.add("no_data", "the study has no observations")
        chk.raise_if_any()
    alpha = number(params.get("alpha", 0.05))
    if alpha is None or not 0 < alpha < 1:
        chk.add("invalid_parameter", "alpha must be between 0 and 1", field="alpha")
        alpha = 0.05
    cells = balanced_cells(chk, obs, KEYS, categorical=True)
    ops, parts, trials = require_full_factorial(chk, cells, KEYS)
    check_count(chk, design, "operators", len(ops), 1)
    check_count(chk, design, "parts", len(parts), 2)
    check_count(chk, design, "trials", len(trials), 1)

    declared = [label(c) for c in (design.get("categories") or []) if label(c)]
    observed = sorted({v for v in cells.values()}, key=natural)
    if declared:
        if len(set(declared)) != len(declared):
            chk.add("invalid_parameter", "categories must be unique", field="categories")
        for v in observed:
            if v not in declared:
                chk.add("invalid_category", f"value '{v}' is not one of the declared categories", field="value")
    categories = declared or observed

    reference = {label(k): label(v) for k, v in (design.get("reference") or {}).items() if label(k)}
    if reference:
        for part in parts:
            if not reference.get(part):
                chk.add("missing_reference", f"part '{part}' has no reference classification", field="reference")
            elif reference[part] not in categories:
                chk.add("invalid_category", f"reference '{reference[part]}' of part '{part}' is not a category",
                        field="reference")
        for part in reference:
            if part not in parts:
                chk.add("unknown_part", f"reference given for part '{part}' that has no observations",
                        field="reference")
    accept, reject = label(design.get("accept_category")), label(design.get("reject_category"))
    if (accept or reject) and not (accept and reject and accept in categories and reject in categories
                                   and accept != reject):
        chk.add("invalid_parameter", "accept_category and reject_category must be two different declared categories",
                field="accept_category")
    if len(categories) < 2:
        chk.add("insufficient_levels", "at least two categories are required", field="categories")
    chk.raise_if_any()

    warnings: list[str] = []
    rating = lambda o, p, t: cells[(o, p, t)]  # noqa: E731

    within, vs_ref, within_kappa, vs_ref_kappa, ref_matrices = [], [], [], [], []
    for o in ops:
        same = sum(1 for p in parts if len({rating(o, p, t) for t in trials}) == 1)
        within.append({"operator": o, **agreement(same, len(parts), alpha)} if len(trials) > 1 else
                      {"operator": o, "inspected": len(parts), "matched": None, "pct": None})
        within_kappa.append({"operator": o, "fleiss_kappa": fleiss_kappa(
            [[sum(1 for t in trials if rating(o, p, t) == c) for c in categories] for p in parts])
            if len(trials) > 1 else None})
        if reference:
            ok = sum(1 for p in parts if all(rating(o, p, t) == reference[p] for t in trials))
            vs_ref.append({"operator": o, **agreement(ok, len(parts), alpha)})
            kappa, matrix = cohen_kappa([(rating(o, p, t), reference[p]) for p in parts for t in trials], categories)
            vs_ref_kappa.append({"operator": o, "cohen_kappa": kappa})
            ref_matrices.append({"operator": o, "rows": "appraiser", "columns": "reference", "matrix": matrix})

    between = all_vs_ref = None
    pair_kappas, pair_matrices = [], []
    if len(ops) > 1:
        agree = sum(1 for p in parts if len({rating(o, p, t) for o in ops for t in trials}) == 1)
        between = agreement(agree, len(parts), alpha)
        between["fleiss_kappa"] = fleiss_kappa(
            [[sum(1 for o in ops for t in trials if rating(o, p, t) == c) for c in categories] for p in parts])
        for i, a in enumerate(ops):
            for b in ops[i + 1:]:
                kappa, matrix = cohen_kappa([(rating(a, p, t), rating(b, p, t)) for p in parts for t in trials],
                                            categories)
                pair_kappas.append({"pair": f"{a} x {b}", "cohen_kappa": kappa})
                pair_matrices.append({"pair": f"{a} x {b}", "rows": a, "columns": b, "matrix": matrix})
        if reference:
            ok = sum(1 for p in parts if all(rating(o, p, t) == reference[p] for o in ops for t in trials))
            all_vs_ref = agreement(ok, len(parts), alpha)

    effectiveness = []
    if reference and accept and reject:
        for o in ops:
            decisions = [(rating(o, p, t), reference[p]) for p in parts for t in trials
                         if reference[p] in (accept, reject)]
            correct = sum(1 for got, ref in decisions if got == ref)
            rej_opp = sum(1 for _g, ref in decisions if ref == reject)
            acc_opp = sum(1 for _g, ref in decisions if ref == accept)
            misses = sum(1 for got, ref in decisions if ref == reject and got == accept)
            false_alarms = sum(1 for got, ref in decisions if ref == accept and got == reject)
            effectiveness.append({
                "operator": o, "opportunities": len(decisions),
                "effectiveness_pct": 100.0 * correct / len(decisions) if decisions else None,
                "miss_rate_pct": 100.0 * misses / rej_opp if rej_opp else None,
                "false_alarm_rate_pct": 100.0 * false_alarms / acc_opp if acc_opp else None,
            })
        if any(r["miss_rate_pct"] is None for r in effectiveness):
            warnings.append("No reference parts in the reject category: miss rate is undefined")

    def minimum(rows, key):
        vals = [r[key] for r in rows if r.get(key) is not None]
        return min(vals) if vals else None

    metrics = {
        "min_within_pct": minimum(within, "pct"),
        "min_vs_reference_pct": minimum(vs_ref, "pct"),
        "between_pct": between["pct"] if between else None,
        "all_vs_reference_pct": all_vs_ref["pct"] if all_vs_ref else None,
        "min_kappa_vs_reference": minimum(vs_ref_kappa, "cohen_kappa"),
        "min_kappa_between_pairs": minimum(pair_kappas, "cohen_kappa"),
        "fleiss_kappa_between": between["fleiss_kappa"] if between else None,
        "min_effectiveness_pct": minimum(effectiveness, "effectiveness_pct"),
        "max_miss_rate_pct": max((r["miss_rate_pct"] for r in effectiveness if r["miss_rate_pct"] is not None),
                                 default=None),
        "max_false_alarm_rate_pct": max((r["false_alarm_rate_pct"] for r in effectiveness
                                         if r["false_alarm_rate_pct"] is not None), default=None),
    }
    if not reference:
        warnings.append("No reference classification: agreement against the reference was not evaluated")
    distribution = Counter(cells.values())
    return clean({
        "method": METHOD,
        "algorithm_version": VERSION,
        "model": "Attribute agreement: percent agreement (Clopper-Pearson CI), Cohen's and Fleiss' kappa",
        "design": {"operators": ops, "parts": parts, "trials": trials, "categories": categories,
                   "has_reference": bool(reference), "accept_category": accept, "reject_category": reject,
                   "alpha": alpha},
        "metrics": metrics,
        "tables": {"within": within, "within_kappa": within_kappa, "vs_reference": vs_ref,
                   "vs_reference_kappa": vs_ref_kappa, "between": between, "all_vs_reference": all_vs_ref,
                   "pair_kappa": pair_kappas, "effectiveness": effectiveness},
        "intermediate": {"category_counts": {c: distribution.get(c, 0) for c in categories}},
        "charts": {"agreement": {"within": within, "vs_reference": vs_ref},
                   "matrices": {"vs_reference": ref_matrices, "pairs": pair_matrices, "categories": categories}},
        "warnings": warnings,
    })
