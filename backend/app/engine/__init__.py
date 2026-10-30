"""Statistical engine for MSA studies.

Independent of the web layer and the database: it receives plain JSON-compatible data
and returns plain JSON-compatible results, so a stored run can be recomputed and
compared at any time. Each method is a separate module with its own validation, model
and version; there is no generic formula shared across methods.

``VALIDATION`` records the evidence status of each method (see docs/msa/). Only methods
marked VALIDATED have reproduced published reference results and/or an independent
implementation in the automated test suite (tests/test_engine_*.py).
"""

import hashlib
import json
from dataclasses import dataclass
from types import ModuleType

from app.engine import attribute, bias, grr_anova, grr_average_range, grr_nested, linearity, stability, type1
from app.engine.common import DesignError, Issue  # noqa: F401  (re-export)

ENGINE_VERSION = "1.0.0"


@dataclass(frozen=True)
class MethodInfo:
    code: str
    module: ModuleType
    family: str            # VARIABLE_GRR, ATTRIBUTE, BIAS, LINEARITY, STABILITY, TYPE1
    observation_fields: tuple[str, ...]
    validation: str        # VALIDATED | EXPERIMENTAL
    evidence: str
    metrics: tuple[str, ...]

    @property
    def version(self) -> str:
        return self.module.VERSION


_GRR_METRICS = ("pct_sv_grr", "pct_contribution_grr", "pct_tolerance_grr", "ndc", "pct_sv_ev", "pct_sv_av",
                "resolution_pct_tolerance")

METHODS: dict[str, MethodInfo] = {m.code: m for m in [
    MethodInfo("GRR_CROSSED_AR", grr_average_range, "VARIABLE_GRR", ("operator", "part", "trial", "value"),
               "VALIDATED", "AIAG MSA 4th ed. GRR example reproduced; hand calculation",
               _GRR_METRICS + ("ranges_out_of_control",)),
    MethodInfo("GRR_CROSSED_ANOVA", grr_anova, "VARIABLE_GRR", ("operator", "part", "trial", "value"),
               "VALIDATED", "AIAG MSA 4th ed. ANOVA sums of squares reproduced; statsmodels OLS ANOVA",
               _GRR_METRICS + ("interaction_p_value", "operator_p_value")),
    MethodInfo("GRR_NESTED_ANOVA", grr_nested, "VARIABLE_GRR", ("operator", "part", "trial", "value"),
               "VALIDATED", "statsmodels nested OLS ANOVA; hand-calculated example",
               _GRR_METRICS + ("operator_p_value",)),
    MethodInfo("ATTRIBUTE_AGREEMENT", attribute, "ATTRIBUTE", ("operator", "part", "trial", "value"),
               "VALIDATED", "Fleiss (1971) worked example; statsmodels Cohen/Fleiss kappa",
               ("min_within_pct", "min_vs_reference_pct", "between_pct", "all_vs_reference_pct",
                "min_kappa_vs_reference", "min_kappa_between_pairs", "fleiss_kappa_between",
                "min_effectiveness_pct", "max_miss_rate_pct", "max_false_alarm_rate_pct")),
    MethodInfo("BIAS", bias, "BIAS", ("trial", "value"),
               "VALIDATED", "AIAG MSA 4th ed. bias example reproduced; scipy t distribution",
               ("abs_bias", "bias_significant", "pct_bias_tolerance", "p_value")),
    MethodInfo("LINEARITY", linearity, "LINEARITY", ("part", "reference", "trial", "value"),
               "VALIDATED", "AIAG MSA 4th ed. linearity example reproduced; scipy linregress",
               ("abs_slope", "pct_linearity", "slope_significant", "intercept_significant",
                "zero_line_within_bands", "r_squared")),
    MethodInfo("STABILITY", stability, "STABILITY", ("subgroup", "measured_at", "value"),
               "VALIDATED", "AIAG SPC 2nd ed. constants; hand-calculated limits and rule patterns",
               ("stable", "violations", "dispersion_out_of_control", "bias")),
    MethodInfo("TYPE1", type1, "TYPE1", ("trial", "value"),
               "VALIDATED", "Hand calculation of Bosch Booklet 10 formulas; independent recomputation",
               ("cg", "cgk", "abs_bias", "bias_significant", "resolution_pct_tolerance")),
]}


def method(code: str) -> MethodInfo:
    if code not in METHODS:
        raise DesignError([Issue("unknown_method", f"unknown MSA method '{code}'")])
    return METHODS[code]


def canonical(data: dict) -> str:
    return json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str)


def input_hash(data: dict) -> str:
    return hashlib.sha256(canonical(data).encode()).hexdigest()


def calculate(code: str, data: dict) -> dict:
    """Validate and compute. Raises :class:`DesignError` listing every problem found."""
    info = method(code)
    result = info.module.calculate(data)
    result["engine_version"] = ENGINE_VERSION
    result["validation_status"] = info.validation
    return result


def catalogue() -> list[dict]:
    return [{"code": m.code, "family": m.family, "algorithm_version": m.version, "validation": m.validation,
             "evidence": m.evidence, "observation_fields": list(m.observation_fields), "metrics": list(m.metrics)}
            for m in METHODS.values()]
