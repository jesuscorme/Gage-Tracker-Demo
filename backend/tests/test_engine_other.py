"""Validation of attribute agreement, bias, linearity, stability and Type 1 methods."""

import numpy as np
import pytest
from scipy import stats
from statsmodels.stats.inter_rater import cohens_kappa, fleiss_kappa as sm_fleiss

from app import engine
from app.engine import DesignError
from app.engine.attribute import cohen_kappa, fleiss_kappa
from app.engine.stability import DEFAULT_RULES, special_causes
from tests.msa_reference import BIAS_AIAG, FLEISS_EXAMPLE, LINEARITY_AIAG, linearity_observations


def run(code, obs, design=None, params=None):
    return engine.calculate(code, {"design": design or {}, "observations": obs, "params": params or {}})


def issues(code, obs, design=None, params=None):
    with pytest.raises(DesignError) as e:
        run(code, obs, design, params)
    return {i.code for i in e.value.issues}


# ---------------------------------------------------------------- attribute agreement

def test_fleiss_kappa_reproduces_published_example_and_statsmodels():
    assert fleiss_kappa(FLEISS_EXAMPLE) == pytest.approx(0.210, abs=5e-4)
    assert fleiss_kappa(FLEISS_EXAMPLE) == pytest.approx(sm_fleiss(np.array(FLEISS_EXAMPLE)), rel=1e-12)


def test_cohen_kappa_hand_example_and_statsmodels():
    # 2x2 example: yes/yes 20, yes/no 5, no/yes 10, no/no 15 -> po = 0.7, pe = 0.5, kappa = 0.4.
    pairs = [("Y", "Y")] * 20 + [("Y", "N")] * 5 + [("N", "Y")] * 10 + [("N", "N")] * 15
    k, m = cohen_kappa(pairs, ["Y", "N"])
    assert k == pytest.approx(0.4) and m == [[20, 5], [10, 15]]
    rng = np.random.default_rng(3)
    for _ in range(10):
        cats = ["A", "B", "C"]
        pairs = [(cats[rng.integers(3)], cats[rng.integers(3)]) for _ in range(60)]
        k, m = cohen_kappa(pairs, cats)
        assert k == pytest.approx(cohens_kappa(np.array(m)).kappa, rel=1e-10)


def attribute_data():
    # 3 appraisers x 2 trials x 6 parts; reference: parts 1-3 G (good), 4-6 NG.
    ref = {str(p): ("G" if p <= 3 else "NG") for p in range(1, 7)}
    ratings = {
        "A": {1: ["G", "G"], 2: ["G", "G"], 3: ["G", "G"], 4: ["NG", "NG"], 5: ["NG", "NG"], 6: ["NG", "NG"]},
        "B": {1: ["G", "G"], 2: ["G", "NG"], 3: ["G", "G"], 4: ["NG", "NG"], 5: ["G", "G"], 6: ["NG", "NG"]},
        "C": {1: ["G", "G"], 2: ["G", "G"], 3: ["NG", "NG"], 4: ["NG", "NG"], 5: ["NG", "NG"], 6: ["NG", "NG"]},
    }
    obs = [{"operator": o, "part": str(p), "trial": t + 1, "value": v}
           for o, parts in ratings.items() for p, vals in parts.items() for t, v in enumerate(vals)]
    return obs, {"categories": ["G", "NG"], "reference": ref, "accept_category": "G", "reject_category": "NG"}


def test_attribute_agreement_hand_counts():
    obs, design = attribute_data()
    r = run("ATTRIBUTE_AGREEMENT", obs, design)
    within = {w["operator"]: w for w in r["tables"]["within"]}
    assert (within["A"]["matched"], within["B"]["matched"], within["C"]["matched"]) == (6, 5, 6)
    vs = {w["operator"]: w for w in r["tables"]["vs_reference"]}
    assert (vs["A"]["matched"], vs["B"]["matched"], vs["C"]["matched"]) == (6, 4, 5)
    # Between appraisers: parts 1, 4, 6 are unanimous across all 6 ratings.
    assert r["tables"]["between"]["matched"] == 3
    assert r["tables"]["all_vs_reference"]["matched"] == 3
    eff = {e["operator"]: e for e in r["tables"]["effectiveness"]}
    # B: 12 decisions, wrong: part 2 trial 2 (false alarm), part 5 x2 (miss) -> 9/12.
    assert eff["B"]["effectiveness_pct"] == pytest.approx(75.0)
    assert eff["B"]["miss_rate_pct"] == pytest.approx(100 * 2 / 6)
    assert eff["B"]["false_alarm_rate_pct"] == pytest.approx(100 * 1 / 6)
    assert eff["A"]["effectiveness_pct"] == 100.0
    # Clopper-Pearson for 5/6 (scipy beta) and kappa of A vs reference = 1.
    lo = stats.beta.ppf(0.025, 5, 2) * 100
    assert within["B"]["ci_low"] == pytest.approx(lo)
    kap = {k["operator"]: k["cohen_kappa"] for k in r["tables"]["vs_reference_kappa"]}
    assert kap["A"] == pytest.approx(1.0)
    assert r["metrics"]["min_vs_reference_pct"] == pytest.approx(100 * 4 / 6)


def test_attribute_validation_uses_categories_not_numbers():
    obs, design = attribute_data()
    bad = obs + [{"operator": "A", "part": "1", "trial": 3, "value": "MAYBE"}]
    found = issues("ATTRIBUTE_AGREEMENT", bad, design)
    assert "invalid_category" in found and "missing_observation" in found
    no_ref = dict(design, reference={"1": "G"})
    assert "missing_reference" in issues("ATTRIBUTE_AGREEMENT", obs, no_ref)
    r = run("ATTRIBUTE_AGREEMENT", obs, {"categories": ["G", "NG"]})
    assert r["tables"]["vs_reference"] == [] and any("No reference" in w for w in r["warnings"])


# ---------------------------------------------------------------- bias

def test_bias_reproduces_aiag_example():
    obs = [{"trial": i + 1, "value": v} for i, v in enumerate(BIAS_AIAG["values"])]
    r = run("BIAS", obs, {"reference": BIAS_AIAG["reference"]})
    s, exp = r["tables"]["summary"], BIAS_AIAG["expected"]
    assert s["bias"] == pytest.approx(exp["bias"], abs=5e-5)
    assert s["s"] == pytest.approx(exp["s"], abs=5e-5)
    assert s["sigma_b"] == pytest.approx(exp["sigma_b"], abs=5e-6)
    assert s["ci_low"] == pytest.approx(exp["ci_low"], abs=5e-5)
    assert s["ci_high"] == pytest.approx(exp["ci_high"], abs=5e-5)
    assert r["metrics"]["bias_significant"] is False
    # Independent check: scipy one-sample t test on the biases.
    t = stats.ttest_1samp(np.array(BIAS_AIAG["values"]) - 6.0, 0.0)
    assert s["p_value"] == pytest.approx(t.pvalue, rel=1e-10)


def test_bias_detects_significant_bias_and_invalid_input():
    obs = [{"trial": i + 1, "value": 6.2 + 0.01 * (i % 3)} for i in range(12)]
    assert run("BIAS", obs, {"reference": 6.0})["metrics"]["bias_significant"] is True
    assert "missing_parameter" in issues("BIAS", obs)
    assert "invalid_value" in issues("BIAS", obs + [{"trial": 99, "value": "x"}], {"reference": 6})
    assert "duplicate_observation" in issues("BIAS", obs + [{"trial": 1, "value": 6.1}], {"reference": 6})


# ---------------------------------------------------------------- linearity

def test_linearity_reproduces_aiag_example_and_scipy():
    r = run("LINEARITY", linearity_observations())
    exp = LINEARITY_AIAG["expected"]
    avgs = [p["average_bias"] for p in r["tables"]["per_part"]]
    assert avgs == pytest.approx(exp["bias_averages"], abs=1e-6)
    m = r["metrics"]
    assert m["slope"] == pytest.approx(exp["slope"], abs=1e-6)
    assert m["intercept"] == pytest.approx(exp["intercept"], abs=1e-6)
    assert m["r_squared"] == pytest.approx(exp["r_squared"], abs=0.005)
    # AIAG conclusion: the bias = 0 line is not inside the bands -> linearity problem.
    assert m["zero_line_within_bands"] is False and m["slope_significant"] is True
    obs = linearity_observations()
    lr = stats.linregress([o["reference"] for o in obs], [o["value"] - o["reference"] for o in obs])
    assert m["slope_p_value"] == pytest.approx(lr.pvalue, rel=1e-8)
    assert m["slope"] == pytest.approx(lr.slope, rel=1e-12)


def test_linearity_requires_consistent_references():
    obs = linearity_observations()
    obs[0] = obs[0] | {"reference": 2.5}
    assert "inconsistent_reference" in issues("LINEARITY", obs)
    single = [o for o in linearity_observations() if o["reference"] == 2.0]
    assert "insufficient_levels" in issues("LINEARITY", single)


# ---------------------------------------------------------------- stability

def test_individuals_chart_hand_calculation():
    obs = [{"subgroup": i + 1, "value": v} for i, v in enumerate([10, 12, 11, 13, 12])]
    r = run("STABILITY", obs, {"subgroup_size": 1, "reference": 11.5})
    loc = r["charts"]["location"]
    # MR = 2,1,2,1 -> MR-bar 1.5; CL 11.6; limits 11.6 +/- 2.660*1.5 (AIAG SPC App. E).
    assert loc["center"] == pytest.approx(11.6)
    assert loc["ucl"] == pytest.approx(11.6 + 2.660 * 1.5) and loc["lcl"] == pytest.approx(11.6 - 2.660 * 1.5)
    assert r["metrics"]["sigma"] == pytest.approx(1.5 / 1.128)
    assert r["charts"]["dispersion"]["ucl"] == pytest.approx(3.267 * 1.5)
    assert r["metrics"]["bias"] == pytest.approx(0.1)
    assert r["metrics"]["stable"] is True


def test_xbar_r_chart_hand_calculation():
    groups = [[1, 2, 3], [2, 3, 4], [3, 4, 5]]
    obs = [{"subgroup": g + 1, "value": v} for g, vals in enumerate(groups) for v in vals]
    r = run("STABILITY", obs, {"subgroup_size": 3})
    loc, disp = r["charts"]["location"], r["charts"]["dispersion"]
    assert loc["center"] == pytest.approx(3) and loc["ucl"] == pytest.approx(3 + 1.023 * 2)
    assert disp["center"] == pytest.approx(2) and disp["ucl"] == pytest.approx(2.574 * 2) and disp["lcl"] == 0
    assert r["metrics"]["sigma"] == pytest.approx(2 / 1.693)


def rules(**enabled):
    cfg = {k: dict(v, enabled=False) for k, v in DEFAULT_RULES.items()}
    for k, v in enabled.items():
        cfg[k.strip("r")]["enabled"] = v
    return cfg


def test_special_cause_criteria_patterns():
    assert special_causes([0, 3.5, 0], 0, 1, rules(r1=True)) == [{"rule": "1", "index": 1}]
    run7 = [0.5] * 7
    assert {"rule": "2", "index": 6} in special_causes(run7, 0, 1, rules(r2=True))
    assert special_causes([0.5] * 6, 0, 1, rules(r2=True)) == []
    assert {"rule": "3", "index": 5} in special_causes([1, 2, 3, 4, 5, 6], 0, 10, rules(r3=True))
    assert special_causes([1, 2, 3, 3, 5, 6], 0, 10, rules(r3=True)) == []
    alt = [0, 1] * 7
    assert special_causes(alt, 0.5, 10, rules(r4=True))[0] == {"rule": "4", "index": 13}
    assert special_causes([2.5, 0, 2.5], 0, 1, rules(r5=True)) == [{"rule": "5", "index": 2}]
    assert special_causes([2.5, 0, -2.5], 0, 1, rules(r5=True)) == []
    assert special_causes([1.5, 1.5, 0, 1.5, 1.5], 0, 1, rules(r6=True)) == [{"rule": "6", "index": 4}]
    assert special_causes([0.1] * 15, 0, 1, rules(r7=True)) == [{"rule": "7", "index": 14}]
    assert special_causes([1.5, -1.5] * 4, 0, 1, rules(r8=True)) == [{"rule": "8", "index": 7}]


def test_stability_rules_are_configurable_and_validated():
    vals = [10.0, 10.2, 9.9, 10.1, 10.0, 10.1, 9.9, 10.0] + [10.05] * 7
    obs = [{"subgroup": i + 1, "value": v} for i, v in enumerate(vals)]
    flagged = run("STABILITY", obs)
    assert any(v["rule"] == "2" for v in flagged["tables"]["violations"])
    relaxed = run("STABILITY", obs, params={"rules": {"2": {"enabled": True, "run": 9}}})
    assert not any(v["rule"] == "2" for v in relaxed["tables"]["violations"])
    assert relaxed["design"]["rules"]["2"]["run"] == 9
    assert "invalid_parameter" in issues("STABILITY", obs, params={"rules": {"99": {"enabled": True}}})
    assert "invalid_parameter" in issues("STABILITY", obs, params={"rules": {"1": {"run": 3}}})
    short = [{"subgroup": 1, "value": 1}, {"subgroup": 1, "value": 2}, {"subgroup": 2, "value": 1}]
    assert "incomplete_subgroup" in issues("STABILITY", short, {"subgroup_size": 2})


# ---------------------------------------------------------------- Type 1

TYPE1_VALUES = [10.002, 9.998, 10.001, 9.999, 10.000, 10.003, 9.997, 10.001, 9.999, 10.000]


def test_type1_hand_calculation():
    obs = [{"trial": i + 1, "value": v} for i, v in enumerate(TYPE1_VALUES)]
    r = run("TYPE1", obs, {"reference": 10.0, "tolerance": 0.1})
    s = np.sqrt(30e-6 / 9)                                   # sum of squared deviations = 30e-6
    assert r["metrics"]["repeatability_sd"] == pytest.approx(s, rel=1e-9)
    assert r["metrics"]["cg"] == pytest.approx(0.02 / (6 * s), rel=1e-9)
    assert r["metrics"]["cgk"] == pytest.approx(0.01 / (3 * s), rel=1e-6)
    shifted = [{"trial": i + 1, "value": v + 0.001} for i, v in enumerate(TYPE1_VALUES)]
    r2 = run("TYPE1", shifted, {"reference": 10.0, "tolerance": 0.1})
    assert r2["metrics"]["bias"] == pytest.approx(0.001, abs=1e-12)
    assert r2["metrics"]["cgk"] == pytest.approx((0.01 - 0.001) / (3 * s), rel=1e-6)
    r3 = run("TYPE1", obs, {"reference": 10.0, "tolerance": 0.1}, {"k_percent": 15, "l_sigma": 4})
    assert r3["metrics"]["cg"] == pytest.approx(0.015 / (4 * s), rel=1e-9)


def test_type1_requires_tolerance_and_handles_zero_spread():
    obs = [{"trial": i + 1, "value": v} for i, v in enumerate(TYPE1_VALUES)]
    assert "missing_parameter" in issues("TYPE1", obs, {"reference": 10.0})
    flat = [{"trial": i + 1, "value": 10.0} for i in range(10)]
    r = run("TYPE1", flat, {"reference": 10.0, "tolerance": 0.1})
    assert r["metrics"]["cg"] is None and any("undefined" in w for w in r["warnings"])
