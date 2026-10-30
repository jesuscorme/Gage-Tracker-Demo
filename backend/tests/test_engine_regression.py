"""Statistical regression: the engine's complete output on the reference datasets is frozen.

``msa_golden.json`` holds the full results (metrics, tables, charts, intermediates) produced
by algorithm version 1.0.0. A change in any number, or in the algorithm version, fails
this test: an engine change must be deliberate, bump the method version and regenerate
the file (``python -m tests.test_engine_regression --update``) after the validation
tests pass again.
"""

import json
import math
import pathlib
import sys

import pytest

from app import engine
from tests.msa_reference import BIAS_AIAG, grr_observations, linearity_observations
from tests.test_engine_grr import NESTED_HAND
from tests.test_engine_other import TYPE1_VALUES, attribute_data

GOLDEN = pathlib.Path(__file__).with_name("msa_golden.json")


def cases() -> dict:
    att_obs, att_design = attribute_data()
    return {
        "GRR_CROSSED_AR": {"design": {"tolerance": 4.0}, "observations": grr_observations(), "params": {}},
        "GRR_CROSSED_ANOVA": {"design": {"tolerance": 4.0}, "observations": grr_observations(), "params": {}},
        "GRR_NESTED_ANOVA": {"design": {}, "params": {},
                             "observations": [{"operator": o, "part": p, "trial": t, "value": v}
                                              for o, p, t, v in NESTED_HAND]},
        "ATTRIBUTE_AGREEMENT": {"design": att_design, "observations": att_obs, "params": {}},
        "BIAS": {"design": {"reference": BIAS_AIAG["reference"]}, "params": {},
                 "observations": [{"trial": i + 1, "value": v} for i, v in enumerate(BIAS_AIAG["values"])]},
        "LINEARITY": {"design": {}, "observations": linearity_observations(), "params": {}},
        "STABILITY": {"design": {"subgroup_size": 1, "reference": 11.5}, "params": {},
                      "observations": [{"subgroup": i + 1, "value": v}
                                       for i, v in enumerate([10, 12, 11, 13, 12, 11, 12, 10, 11, 12])]},
        "TYPE1": {"design": {"reference": 10.0, "tolerance": 0.1}, "params": {},
                  "observations": [{"trial": i + 1, "value": v} for i, v in enumerate(TYPE1_VALUES)]},
    }


def compare(expected, actual, path="") -> list[str]:
    if isinstance(expected, dict):
        if set(expected) != set(actual):
            return [f"{path}: keys {sorted(set(expected) ^ set(actual))}"]
        return [d for k in expected for d in compare(expected[k], actual[k], f"{path}.{k}")]
    if isinstance(expected, list):
        if len(expected) != len(actual):
            return [f"{path}: length {len(expected)} != {len(actual)}"]
        return [d for i, (e, a) in enumerate(zip(expected, actual)) for d in compare(e, a, f"{path}[{i}]")]
    if isinstance(expected, float) and isinstance(actual, (int, float)) and not isinstance(actual, bool):
        ok = math.isclose(expected, actual, rel_tol=1e-12, abs_tol=1e-14)
        return [] if ok else [f"{path}: {expected!r} != {actual!r}"]
    return [] if expected == actual else [f"{path}: {expected!r} != {actual!r}"]


@pytest.mark.parametrize("method", list(engine.METHODS))
def test_engine_output_matches_frozen_results(method):
    golden = json.loads(GOLDEN.read_text(encoding="utf-8"))
    data = cases()[method]
    assert golden[method]["input_hash"] == engine.input_hash(data)
    result = json.loads(json.dumps(engine.calculate(method, data)))
    diffs = compare(golden[method]["result"], result)
    assert not diffs, "\n".join(diffs[:20])


if __name__ == "__main__" and "--update" in sys.argv:
    out = {m: {"input_hash": engine.input_hash(d), "result": json.loads(json.dumps(engine.calculate(m, d)))}
           for m, d in cases().items()}
    GOLDEN.write_text(json.dumps(out, indent=1, sort_keys=True), encoding="utf-8")
    print("updated", GOLDEN)


@pytest.mark.parametrize("method", list(engine.METHODS))
@pytest.mark.parametrize("lang", ["es", "en"])
def test_msa_pdf_report_renders_for_every_method(method, lang):
    """The study report (tables + charts) renders for every methodology and language."""
    from app.modules.msa.report_pdf import render

    data = cases()[method]
    result = engine.calculate(method, data)
    snap = {"organization": "Org", "study_code": "MSA-1", "revision": 1, "issued_on": "2026-10-30", "title": method,
            "method": method, "family": engine.method(method).family, "characteristic": "C", "part_number": None,
            "part_revision": None, "customer": None, "plant": "P1", "department": None,
            "gage": {"gage_code": "G", "description": "D", "status": "CALIBRATED", "next_due_date": None},
            "responsible": "R", "start_date": "2026-10-30", "end_date": None, "operators": [], "run_number": 1,
            "engine_version": result["engine_version"], "algorithm_version": result["algorithm_version"],
            "validation_status": result["validation_status"], "input_hash": engine.input_hash(data), "input": data,
            "results": result, "criteria": None, "evaluation": None, "decision": "NO_CRITERIA",
            "final_decision": None, "final_comment": None, "concluded_by": None, "calculated_by": "R",
            "calculated_at": "2026-10-30T10:00:00", "lang": lang}
    pdf = render(snap)
    assert pdf.startswith(b"%PDF") and len(pdf) > 3000
