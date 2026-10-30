"""Validation of the variable GRR methods (crossed Average & Range, crossed ANOVA, nested ANOVA).

Evidence used: published AIAG results, an independent implementation (statsmodels OLS
ANOVA) on the reference data and on random balanced designs, and hand calculations.
"""

import json
import random

import numpy as np
import pandas as pd
import pytest
from statsmodels.formula.api import ols
from statsmodels.stats.anova import anova_lm

from app import engine
from app.engine import DesignError
from tests.msa_reference import (GRR_AIAG, GRR_AIAG_ANOVA_SS, GRR_AIAG_AR, GRR_AIAG_AVERAGES, GRR_AIAG_RANGES,
                                 grr_observations)


def run(code, obs, design=None, params=None):
    return engine.calculate(code, {"design": design or {}, "observations": obs, "params": params or {}})


def issues(code, obs, design=None, params=None):
    with pytest.raises(DesignError) as e:
        run(code, obs, design, params)
    return {i.code for i in e.value.issues}


# ---------------------------------------------------------------- Average & Range

def test_average_range_reproduces_aiag_example():
    r = run("GRR_CROSSED_AR", grr_observations(), {"operators": 3, "parts": 10, "trials": 3})
    m, inter = r["metrics"], r["intermediate"]
    ops = {row["operator"]: row for row in r["tables"]["operators"]}
    for op in "ABC":
        assert ops[op]["average"] == pytest.approx(GRR_AIAG_AVERAGES[op], abs=5e-5)
        assert ops[op]["average_range"] == pytest.approx(GRR_AIAG_RANGES[op], abs=5e-4)
    assert inter["r_bar"] == pytest.approx(GRR_AIAG_AR["r_bar"], abs=5e-5)
    assert inter["x_diff"] == pytest.approx(GRR_AIAG_AR["x_diff"], abs=1e-4)
    assert inter["rp"] == pytest.approx(GRR_AIAG_AR["rp"], abs=5e-4)
    # The manual carries R-bar = 0.3417 and Rp = 3.511 rounded; differences stay below 1e-4.
    for key in ("ev", "av", "grr", "pv", "tv"):
        assert m[key] == pytest.approx(GRR_AIAG_AR[key], abs=1e-4), key
    assert m["pct_sv_ev"] == pytest.approx(GRR_AIAG_AR["pct_ev"], abs=0.01)
    assert m["pct_sv_av"] == pytest.approx(GRR_AIAG_AR["pct_av"], abs=0.01)
    assert m["pct_sv_grr"] == pytest.approx(GRR_AIAG_AR["pct_grr"], abs=0.01)
    assert m["pct_sv_pv"] == pytest.approx(GRR_AIAG_AR["pct_pv"], abs=0.01)
    assert m["ndc"] == GRR_AIAG_AR["ndc"]
    assert r["validation_status"] == "VALIDATED" and r["algorithm_version"] == "1.0.0"


def test_average_range_tolerance_and_multiplier():
    r6 = run("GRR_CROSSED_AR", grr_observations(), {"tolerance": 6.0})
    assert r6["metrics"]["pct_tolerance_grr"] == pytest.approx(100 * 6 * r6["metrics"]["grr"] / 6.0)
    r515 = run("GRR_CROSSED_AR", grr_observations(), {"tolerance": 6.0}, {"study_var_multiplier": 5.15})
    assert r515["metrics"]["pct_tolerance_grr"] == pytest.approx(100 * 5.15 * r6["metrics"]["grr"] / 6.0)
    # %SV does not depend on the multiplier.
    assert r515["metrics"]["pct_sv_grr"] == pytest.approx(r6["metrics"]["pct_sv_grr"])
    assert "invalid_parameter" in issues("GRR_CROSSED_AR", grr_observations(), params={"study_var_multiplier": 4})


def test_average_range_rejects_designs_outside_tabulated_constants():
    obs = grr_observations() + [{"operator": "D", "part": str(p), "trial": t, "value": 0.1}
                                for p in range(1, 11) for t in (1, 2, 3)]
    assert "too_many_levels" in issues("GRR_CROSSED_AR", obs)          # K2 only for 2-3 appraisers
    assert "too_many_levels" in run_issues_parts(11)


def run_issues_parts(n):
    obs = [{"operator": o, "part": str(p), "trial": t, "value": p + 0.01 * t}
           for o in "AB" for p in range(1, n + 1) for t in (1, 2)]
    return issues("GRR_CROSSED_AR", obs)


# ---------------------------------------------------------------- crossed ANOVA

def statsmodels_ss(obs):
    df = pd.DataFrame(obs)
    model = ols("value ~ C(part) * C(operator)", data=df).fit()
    return anova_lm(model, typ=2)


def test_anova_reproduces_aiag_sums_of_squares_and_statsmodels():
    r = run("GRR_CROSSED_ANOVA", grr_observations(), params={"interaction_mode": "include"})
    full = r["intermediate"]["anova_full"]
    exp = GRR_AIAG_ANOVA_SS
    assert full["ss_o"] == pytest.approx(exp["Appraiser"][1], abs=1e-4) and full["df_o"] == exp["Appraiser"][0]
    assert full["ss_p"] == pytest.approx(exp["Parts"][1], abs=1e-4) and full["df_p"] == exp["Parts"][0]
    assert full["ss_po"] == pytest.approx(exp["Appraiser x Part"][1], abs=1e-4)
    assert full["ss_e"] == pytest.approx(exp["Equipment"][1], abs=1e-4) and full["df_e"] == exp["Equipment"][0]
    assert full["ss_t"] == pytest.approx(exp["Total"][1], abs=1e-4) and full["df_t"] == exp["Total"][0]

    sm = statsmodels_ss(grr_observations())
    assert full["ss_p"] == pytest.approx(sm.loc["C(part)", "sum_sq"], rel=1e-10)
    assert full["ss_o"] == pytest.approx(sm.loc["C(operator)", "sum_sq"], rel=1e-10)
    assert full["ss_po"] == pytest.approx(sm.loc["C(part):C(operator)", "sum_sq"], rel=1e-10)
    assert full["ss_e"] == pytest.approx(sm.loc["Residual", "sum_sq"], rel=1e-10)
    # statsmodels' F for the interaction uses MS_E as denominator, as the random model does.
    assert full["p_interaction"] == pytest.approx(sm.loc["C(part):C(operator)", "PR(>F)"], rel=1e-8)


def test_anova_interaction_pooling_rule():
    auto = run("GRR_CROSSED_ANOVA", grr_observations())
    # AIAG example: interaction F = 0.434, p ~ 0.97 > 0.25 -> pooled (reduced model).
    assert auto["metrics"]["interaction_in_model"] is False
    assert auto["metrics"]["interaction_p_value"] > 0.25
    sources = [row["source"] for row in auto["tables"]["anova"]]
    assert "Part x Operator" not in sources
    full = auto["intermediate"]["anova_full"]
    ms_pool = (full["ss_po"] + full["ss_e"]) / (full["df_po"] + full["df_e"])
    vc = auto["intermediate"]["variance_components"]
    assert vc["repeatability"] == pytest.approx(ms_pool)
    assert vc["operator"] == pytest.approx((full["ms_o"] - ms_pool) / (10 * 3))
    assert vc["part"] == pytest.approx((full["ms_p"] - ms_pool) / (3 * 3))
    assert auto["metrics"]["grr"] == pytest.approx(np.sqrt(vc["repeatability"] + vc["operator"]))

    included = run("GRR_CROSSED_ANOVA", grr_observations(), params={"interaction_mode": "include"})
    assert included["metrics"]["interaction_in_model"] is True
    vc2 = included["intermediate"]["variance_components"]
    # MS_PO < MS_E here, so the interaction component is truncated at zero.
    assert vc2["interaction"] == 0.0
    assert any("negative variance" in w for w in included["warnings"])


@pytest.mark.parametrize("seed", range(12))
def test_anova_matches_statsmodels_on_random_designs(seed):
    rng = np.random.default_rng(seed)
    o, p, t = int(rng.integers(2, 5)), int(rng.integers(2, 11)), int(rng.integers(2, 5))
    part_eff = rng.normal(0, 2, p)
    op_eff = rng.normal(0, 0.5, o)
    inter = rng.normal(0, rng.choice([0.0, 0.8]), (o, p))
    obs = [{"operator": f"O{i}", "part": f"P{j}", "trial": k + 1,
            "value": float(10 + part_eff[j] + op_eff[i] + inter[i, j] + rng.normal(0, 0.3))}
           for i in range(o) for j in range(p) for k in range(t)]
    random.Random(seed).shuffle(obs)                 # input order must not matter
    r = run("GRR_CROSSED_ANOVA", obs, params={"interaction_mode": "include"})
    full, vc = r["intermediate"]["anova_full"], r["intermediate"]["variance_components"]
    sm = statsmodels_ss(obs)
    ms = {k: sm.loc[k, "sum_sq"] / sm.loc[k, "df"] for k in sm.index}
    assert full["ss_p"] == pytest.approx(sm.loc["C(part)", "sum_sq"], rel=1e-9)
    assert full["ss_e"] == pytest.approx(sm.loc["Residual", "sum_sq"], rel=1e-9)
    exp_int = max((ms["C(part):C(operator)"] - ms["Residual"]) / t, 0)
    exp_op = max((ms["C(operator)"] - ms["C(part):C(operator)"]) / (p * t), 0)
    exp_part = max((ms["C(part)"] - ms["C(part):C(operator)"]) / (o * t), 0)
    assert vc["interaction"] == pytest.approx(exp_int, abs=1e-12)
    assert vc["operator"] == pytest.approx(exp_op, abs=1e-12)
    assert vc["part"] == pytest.approx(exp_part, abs=1e-12)
    m = r["metrics"]
    tv2 = ms["Residual"] + exp_int + exp_op + exp_part
    assert m["pct_contribution_grr"] == pytest.approx(100 * (ms["Residual"] + exp_int + exp_op) / tv2)


# ---------------------------------------------------------------- nested ANOVA

NESTED_HAND = [  # operator A measures parts 1-2, B measures parts 3-4, 2 trials
    ("A", "1", 1, 10), ("A", "1", 2, 12), ("A", "2", 1, 14), ("A", "2", 2, 16),
    ("B", "3", 1, 20), ("B", "3", 2, 22), ("B", "4", 1, 18), ("B", "4", 2, 20),
]


def nested_obs(rows=NESTED_HAND):
    return [{"operator": o, "part": p, "trial": t, "value": v} for o, p, t, v in rows]


def test_nested_hand_calculation():
    r = run("GRR_NESTED_ANOVA", nested_obs(), {"operators": 2, "parts_per_operator": 2, "trials": 2})
    t = r["intermediate"]["anova_full"]
    # SS_O = 2*2*((13-16.5)^2 + (20-16.5)^2) = 98; SS_P(O) = 2*(4+4+1+1) = 20; SS_E = 8; SS_T = 126.
    assert (t["ss_o"], t["ss_p_in_o"], t["ss_e"], t["ss_t"]) == pytest.approx((98, 20, 8, 126))
    vc = r["intermediate"]["variance_components"]
    # var_e = 2; var_p = (10 - 2)/2 = 4; var_o = (98 - 10)/(2*2) = 22.
    assert (vc["repeatability"], vc["part_in_operator"], vc["operator"]) == pytest.approx((2, 4, 22))
    m = r["metrics"]
    assert m["grr"] == pytest.approx(np.sqrt(24)) and m["pv"] == pytest.approx(2.0)
    assert m["pct_sv_grr"] == pytest.approx(100 * np.sqrt(24 / 28))
    assert m["ndc"] == 0                                   # floor(1.41 * 2 / 4.899)


@pytest.mark.parametrize("seed", range(8))
def test_nested_matches_statsmodels_sequential_anova(seed):
    rng = np.random.default_rng(100 + seed)
    o, p, t = int(rng.integers(2, 5)), int(rng.integers(2, 6)), int(rng.integers(2, 4))
    obs = []
    for i in range(o):
        op_eff = rng.normal(0, 1)
        for j in range(p):
            part_eff = rng.normal(0, 2)
            for k in range(t):
                obs.append({"operator": f"O{i}", "part": f"O{i}-P{j}", "trial": k + 1,
                            "value": float(50 + op_eff + part_eff + rng.normal(0, 0.4))})
    r = run("GRR_NESTED_ANOVA", obs)
    df = pd.DataFrame(obs)
    # Extra-sum-of-squares by model comparison. (A single sequential ANOVA with both
    # factors is not used: the nested design matrix is rank deficient and statsmodels'
    # type I sums of squares are then not a valid decomposition.)
    by_op = ols("value ~ C(operator)", data=df).fit()
    by_part = ols("value ~ C(part)", data=df).fit()       # parts nested -> same fit as O + P(O)
    full = r["intermediate"]["anova_full"]
    assert full["ss_o"] == pytest.approx(by_op.ess, rel=1e-9)
    assert full["ss_p_in_o"] == pytest.approx(by_op.ssr - by_part.ssr, rel=1e-9)
    assert full["ss_e"] == pytest.approx(by_part.ssr, rel=1e-9)
    assert full["df_e"] == by_part.df_resid and full["df_p_in_o"] == by_op.df_resid - by_part.df_resid


def test_nested_rejects_crossed_or_unbalanced_data():
    assert "part_not_nested" in issues("GRR_NESTED_ANOVA", grr_observations())
    unbalanced = nested_obs() + [{"operator": "B", "part": "5", "trial": 1, "value": 19},
                                 {"operator": "B", "part": "5", "trial": 2, "value": 19.5}]
    assert "unbalanced_design" in issues("GRR_NESTED_ANOVA", unbalanced)


def test_nested_and_crossed_are_different_models():
    """Same numbers analysed under both structures must not give the same components."""
    obs = nested_obs()
    nested = run("GRR_NESTED_ANOVA", obs)["metrics"]
    relabeled = [o | {"part": {"1": "1", "2": "2", "3": "1", "4": "2"}[o["part"]]} for o in obs]
    crossed = run("GRR_CROSSED_ANOVA", relabeled, params={"interaction_mode": "include"})["metrics"]
    assert nested["grr"] != pytest.approx(crossed["grr"])


# ---------------------------------------------------------------- invalid and incomplete data

def test_incomplete_and_invalid_data_are_reported_together():
    obs = grr_observations()
    obs = obs[1:]                                       # one missing cell
    obs.append(dict(obs[0]))                            # one duplicate
    obs.append({"operator": "A", "part": "", "trial": 1, "value": 1})
    obs.append({"operator": "A", "part": "1", "trial": "x", "value": 1})
    obs.append({"operator": "A", "part": "1", "trial": 4, "value": "abc"})
    found = issues("GRR_CROSSED_ANOVA", obs)
    assert {"missing_observation", "duplicate_observation", "missing_label", "invalid_trial",
            "invalid_value"} <= found


def test_design_declaration_must_match_data_and_minimums():
    assert "design_mismatch" in issues("GRR_CROSSED_ANOVA", grr_observations(), {"parts": 5})
    one_op = [o for o in grr_observations() if o["operator"] == "A"]
    assert "insufficient_levels" in issues("GRR_CROSSED_ANOVA", one_op)
    assert "no_data" in issues("GRR_CROSSED_ANOVA", [])
    assert "invalid_parameter" in issues("GRR_CROSSED_ANOVA", grr_observations(), {"usl": 1, "lsl": 2})


def test_zero_measurement_variation_is_handled_without_numbers_invented():
    obs = [{"operator": o, "part": str(p), "trial": t, "value": float(p)}
           for o in "AB" for p in range(1, 6) for t in (1, 2)]
    r = run("GRR_CROSSED_ANOVA", obs)
    assert r["metrics"]["grr"] == 0 and r["metrics"]["ndc"] is None
    assert any("ndc is undefined" in w for w in r["warnings"])
    json.dumps(r, allow_nan=False)                     # no NaN/inf leak into stored JSON


# ---------------------------------------------------------------- reproducibility and versioning

def test_results_are_reproducible_and_order_independent():
    obs = grr_observations()
    a = run("GRR_CROSSED_ANOVA", obs, {"tolerance": 4})
    shuffled = obs[:]
    random.Random(7).shuffle(shuffled)
    b = run("GRR_CROSSED_ANOVA", shuffled, {"tolerance": 4})
    assert engine.canonical(a) == engine.canonical(b)
    data = {"design": {"tolerance": 4}, "observations": obs, "params": {}}
    reordered = {"params": {}, "observations": obs, "design": {"tolerance": 4}}
    assert engine.input_hash(data) == engine.input_hash(reordered)


def test_catalogue_exposes_versions_and_validation_status():
    cat = {m["code"]: m for m in engine.catalogue()}
    assert set(cat) == {"GRR_CROSSED_AR", "GRR_CROSSED_ANOVA", "GRR_NESTED_ANOVA", "ATTRIBUTE_AGREEMENT", "BIAS",
                        "LINEARITY", "STABILITY", "TYPE1"}
    assert all(m["algorithm_version"] and m["validation"] in ("VALIDATED", "EXPERIMENTAL") for m in cat.values())
    with pytest.raises(DesignError):
        engine.calculate("NOT_A_METHOD", {})


def test_aiag_dataset_sanity():
    assert sum(len(t) for trials in GRR_AIAG.values() for t in trials) == 90
