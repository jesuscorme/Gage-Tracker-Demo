"""AIAG MSA 4th ed. guidance: thresholds of Table II-D 1 (p. 78), ndc (p. 78), Table III-C 6 (p. 140),
kappa (p. 137), bias (pp. 88-89), linearity (p. 98), stability (p. 86); every item cites a page."""

import re

import pytest

from app.modules.msa.guidance import guidance


def levels(method, **metrics):
    return [g["level"] for g in guidance(method, {"metrics": metrics})]


@pytest.mark.parametrize("pct, level", [(9.99, "ok"), (10.0, "warn"), (30.0, "warn"), (30.01, "bad")])
def test_grr_bands_follow_table_ii_d_1(pct, level):
    g = guidance("GRR_CROSSED_ANOVA", {"metrics": {"pct_sv_grr": pct}})
    assert g[0]["level"] == level and "%GRR" in g[0]["es"]
    assert g[-1]["level"] == "info" and "NO es una práctica aceptable" in g[-1]["es"]


@pytest.mark.parametrize("ndc, level", [(5, "ok"), (4, "bad")])
def test_ndc_at_least_five(ndc, level):
    assert levels("GRR_CROSSED_AR", ndc=ndc)[0] == level


def test_dominant_component_recommendation_only_when_grr_is_not_acceptable():
    assert not any("Domina" in g["es"] for g in guidance("GRR_CROSSED_AR", {"metrics": {
        "pct_sv_grr": 8, "pct_sv_ev": 7, "pct_sv_av": 3}}))
    ev = guidance("GRR_CROSSED_AR", {"metrics": {"pct_sv_grr": 20, "pct_sv_ev": 18, "pct_sv_av": 8}})
    av = guidance("GRR_CROSSED_AR", {"metrics": {"pct_sv_grr": 20, "pct_sv_ev": 8, "pct_sv_av": 18}})
    assert any("repetibilidad" in g["es"] for g in ev)
    assert any("reproducibilidad" in g["es"] for g in av)


@pytest.mark.parametrize("metrics, expected", [
    ({"min_effectiveness_pct": 90, "max_miss_rate_pct": 2, "max_false_alarm_rate_pct": 5}, ["ok", "ok", "ok"]),
    ({"min_effectiveness_pct": 80, "max_miss_rate_pct": 5, "max_false_alarm_rate_pct": 10}, ["warn", "warn", "warn"]),
    ({"min_effectiveness_pct": 79.9, "max_miss_rate_pct": 5.1, "max_false_alarm_rate_pct": 10.1}, ["bad", "bad", "bad"]),
])
def test_attribute_effectiveness_table_iii_c_6(metrics, expected):
    assert levels("ATTRIBUTE_AGREEMENT", **metrics) == expected


@pytest.mark.parametrize("kappa, level", [(0.76, "ok"), (0.75, "warn"), (0.4, "warn"), (0.39, "bad")])
def test_kappa_guideline(kappa, level):
    assert levels("ATTRIBUTE_AGREEMENT", min_kappa_vs_reference=kappa) == [level]


def test_location_and_stability_methods():
    assert levels("BIAS", bias_significant=False) == ["ok"]
    assert levels("BIAS", bias_significant=True) == ["bad", "info"]
    assert levels("LINEARITY", zero_line_within_bands=True) == ["ok"]
    assert levels("LINEARITY", zero_line_within_bands=False) == ["bad"]
    assert levels("STABILITY", stable=True) == ["ok"]
    assert levels("STABILITY", stable=False) == ["bad"]
    assert levels("BIAS") == [] and guidance("UNKNOWN", {"metrics": {}}) == []


def test_every_item_is_bilingual_without_references():
    samples = {"GRR_CROSSED_AR": {"pct_sv_grr": 40, "ndc": 2, "pct_sv_ev": 30, "pct_sv_av": 20, "ranges_out_of_control": 1},
               "BIAS": {"bias_significant": True}, "LINEARITY": {"zero_line_within_bands": False},
               "STABILITY": {"stable": False}, "ATTRIBUTE_AGREEMENT": {"min_effectiveness_pct": 85,
                                                                      "min_kappa_vs_reference": 0.5},
               }
    for method, m in samples.items():
        for g in guidance(method, {"metrics": m}):
            assert g["es"] and g["en"] and set(g) == {"level", "es", "en"}
            assert not re.search(r"AIAG|[Mm]anual|\bpp?\. \d", g["es"] + g["en"])
            assert g["level"] in {"ok", "warn", "bad", "info"}
    assert guidance("TYPE1", {"metrics": {"cg": 1.5}}) == []
