"""Interpretation and recommendations for an MSA result, paraphrasing the AIAG MSA Reference
Manual, 4th ed. (Spanish edition kept in the repository as "13. Manual MSA 4ta Ed.pdf").

Every item carries the manual page it comes from; anything not taken from the manual is labelled
as such. Guidance is derived on read from the stored metrics: it never changes a run, its
evaluation or its decision, which remain governed by the organization's approved criteria."""

GUIDANCE_VERSION = "1.0.0"

_MSA = {"es": "Manual MSA (AIAG, 4.ª ed., versión en español)", "en": "AIAG MSA Manual, 4th ed. (Spanish edition)"}


def _ref(es: str, en: str | None = None) -> dict:
    return {"es": f"{_MSA['es']}, {es}", "en": f"{_MSA['en']}, {en or es}"}


def _item(level: str, es: str, en: str, ref: dict) -> dict:
    return {"level": level, "es": es, "en": en, "ref": ref}


def _fmt(v: float) -> str:
    return f"{v:.2f}"


def _grr(m: dict) -> list[dict]:
    out = []
    table = _ref("Tabla II-D 1, p. 78", "Table II-D 1, p. 78")
    g = m.get("pct_sv_grr")
    if g is not None:
        if g < 10:
            out.append(_item("ok", f"%GRR = {_fmt(g)} %, abajo del 10 %: generalmente aceptable. Recomendado, sobre todo "
                                   "para clasificar partes o cuando se requiere un control cerrado del proceso.",
                             f"%GRR = {_fmt(g)} %, under 10 %: generally acceptable. Recommended, especially to sort "
                             "parts or when tight process control is required.", table))
        elif g <= 30:
            out.append(_item("warn", f"%GRR = {_fmt(g)} %, entre 10 y 30 %: puede ser aceptable para algunas aplicaciones. "
                                     "Decidir según la importancia de la medición, el costo del dispositivo y el de "
                                     "retrabajos o reparaciones. Debe aprobarlo el cliente.",
                             f"%GRR = {_fmt(g)} %, 10 to 30 %: may be acceptable for some applications, based on the "
                             "importance of the measurement, gage cost and rework or repair cost. Should be approved "
                             "by the customer.", table))
        else:
            out.append(_item("bad", f"%GRR = {_fmt(g)} %, arriba del 30 %: se considera inaceptable. Hacer todo esfuerzo "
                                    "por mejorar el sistema de medición; mientras tanto puede usarse una estrategia de "
                                    "medición, p. ej. promediar varias lecturas de la misma característica.",
                             f"%GRR = {_fmt(g)} %, over 30 %: unacceptable. Every effort should be made to improve the "
                             "measurement system; meanwhile a measurement strategy may help, e.g. averaging several "
                             "readings of the same characteristic.", table))
    ndc = m.get("ndc")
    if ndc is not None:
        ok = ndc >= 5
        out.append(_item("ok" if ok else "bad",
                         f"ndc = {ndc:g}: {'cumple' if ok else 'no cumple'} el valor recomendado (≥ 5).",
                         f"ndc = {ndc:g}: {'meets' if ok else 'does not meet'} the recommended value (≥ 5).",
                         _ref("Cap. II, Secc. D, p. 78", "Ch. II, Sec. D, p. 78")))
    ev, av = m.get("pct_sv_ev"), m.get("pct_sv_av")
    if g is not None and g >= 10 and ev is not None and av is not None:
        page = _ref("Cap. III, Secc. B, Análisis de estudios RRG, p. 128", "Ch. III, Sec. B, Analysis of GRR studies, p. 128")
        if ev >= av:
            out.append(_item("info", f"Domina la repetibilidad (EV {_fmt(ev)} % vs AV {_fmt(av)} %). Revisar: mantenimiento "
                                     "del instrumento, rigidez del gage, sujeción o localización, variación dentro de la parte.",
                             f"Repeatability dominates (EV {_fmt(ev)} % vs AV {_fmt(av)} %). Check: instrument maintenance, "
                             "gage rigidity, clamping or location, within-part variation.", page))
        else:
            out.append(_item("info", f"Domina la reproducibilidad (AV {_fmt(av)} % vs EV {_fmt(ev)} %). Revisar: entrenamiento "
                                     "de evaluadores en uso y lectura, claridad de la escala del gage, un dispositivo que "
                                     "ayude a usarlo de forma consistente.",
                             f"Reproducibility dominates (AV {_fmt(av)} % vs EV {_fmt(ev)} %). Check: appraiser training "
                             "in using and reading the gage, gage dial clarity, a fixture to help use it consistently.", page))
    if m.get("ranges_out_of_control"):
        out.append(_item("warn", f"{m['ranges_out_of_control']} rango(s) fuera de control: revisar la consistencia de cada "
                                 "evaluador antes de interpretar el %GRR.",
                         f"{m['ranges_out_of_control']} range(s) out of control: review each appraiser's consistency "
                         "before interpreting %GRR.", _ref("Cap. III, Secc. B, gráfica de rangos, p. 108",
                                                           "Ch. III, Sec. B, range chart, p. 108")))
    out.append(_item("info", "Usar la guía de %GRR como único criterio NO es una práctica aceptable; los criterios finales "
                             "dependen del propósito del sistema y deben acordarse con el cliente.",
                     "Using the %GRR guideline alone is NOT acceptable practice; final criteria depend on the purpose "
                     "of the system and should be agreed with the customer.", _ref("Cap. II, Secc. D, pp. 77-78",
                                                                                     "Ch. II, Sec. D, pp. 77-78")))
    return out


def _bias(m: dict) -> list[dict]:
    sig = m.get("bias_significant")
    if sig is None:
        return []
    if not sig:
        return [_item("ok", "El sesgo es aceptable (estadísticamente cero): el cero cae dentro del intervalo de confianza.",
                      "Bias is acceptable (statistically zero): zero lies within the confidence interval.",
                      _ref("Cap. III, Secc. B, pp. 88-89", "Ch. III, Sec. B, pp. 88-89"))]
    return [
        _item("bad", "El sesgo es estadísticamente distinto de cero. Investigar: error del master o valor de referencia, "
                     "instrumento desgastado, dimensiones o característica equivocadas, calibración inapropiada, "
                     "uso inapropiado por el evaluador, algoritmo de corrección incorrecto.",
              "Bias is statistically non-zero. Investigate: master or reference value error, worn instrument, wrong "
              "dimension or characteristic, improper calibration, improper use by the appraiser, wrong correction "
              "algorithm.", _ref("Cap. III, Secc. B, Análisis de estudios de sesgo, p. 95",
                                 "Ch. III, Sec. B, Analysis of bias studies, p. 95")),
        _item("info", "Recalibrar para llevar el sesgo a cero. Si no es posible, corregir cada lectura por el sesgo solo "
                      "con la concurrencia del cliente, por el riesgo de error del evaluador.",
              "Recalibrate to bring bias to zero. If not possible, correct each reading for bias only with the "
              "customer's concurrence, given the risk of appraiser error.", _ref("p. 95")),
    ]


def _linearity(m: dict) -> list[dict]:
    inside = m.get("zero_line_within_bands")
    if inside is None:
        return []
    if inside:
        return [_item("ok", "La línea «sesgo = 0» queda totalmente dentro de las bandas de confianza: linealidad aceptable.",
                      "The \"bias = 0\" line lies entirely within the confidence bands: linearity is acceptable.",
                      _ref("Cap. III, Secc. B, p. 98", "Ch. III, Sec. B, p. 98"))]
    return [_item("bad", "La línea «sesgo = 0» sale de las bandas de confianza: linealidad no aceptable. Posibles causas: "
                         "calibración que no cubre el rango de operación, masters desgastados o con error en mínimo/máximo, "
                         "instrumento desgastado o con mantenimiento deficiente, gage equivocado para la aplicación.",
                  "The \"bias = 0\" line leaves the confidence bands: linearity is not acceptable. Possible causes: "
                  "calibration not covering the operating range, worn masters or min/max master error, worn or poorly "
                  "maintained instrument, wrong gage for the application.",
                  _ref("p. 98; causas en Cap. I, Secc. E, pp. 53-54", "p. 98; causes in Ch. I, Sec. E, pp. 53-54"))]


def _stability(m: dict) -> list[dict]:
    stable = m.get("stable")
    if stable is None:
        return []
    if stable:
        return [_item("ok", "Sin causas especiales: el sistema es estable. No existe un índice numérico de estabilidad; "
                            "los datos pueden usarse para estimar el sesgo y aproximar la repetibilidad.",
                      "No special causes: the system is stable. There is no numeric stability index; the data can be "
                      "used to estimate bias and approximate repeatability.",
                      _ref("Cap. III, Secc. B, p. 86", "Ch. III, Sec. B, p. 86"))]
    return [_item("bad", "Hay causas especiales: el sistema no es estable y debe estabilizarse antes de cualquier otro "
                         "análisis. Revisar: calibración o su intervalo, desgaste, mantenimiento, master, medio ambiente, "
                         "método de medición.",
                  "Special causes present: the system is not stable and must be stabilized before any further "
                  "analysis. Check: calibration or its interval, wear, maintenance, master, environment, measurement method.",
                  _ref("p. 77; causas en Cap. I, Secc. E, p. 52", "p. 77; causes in Ch. I, Sec. E, p. 52"))]


def _band(value, good, marginal, higher_is_better: bool) -> str:
    if higher_is_better:
        return "ok" if value >= good else "warn" if value >= marginal else "bad"
    return "ok" if value <= good else "warn" if value <= marginal else "bad"


def _attribute(m: dict) -> list[dict]:
    out = []
    table = _ref("Tabla III-C 6, p. 140", "Table III-C 6, p. 140")
    word = {"ok": ("aceptable", "acceptable"), "warn": ("marginal, puede requerir mejora", "marginal, may need improvement"),
            "bad": ("no aceptable, requiere mejora", "unacceptable, needs improvement")}
    for key, es, en, good, marginal, hib, sym in (
            ("min_effectiveness_pct", "Efectividad mínima", "Lowest effectiveness", 90, 80, True, "≥ 90 %"),
            ("max_miss_rate_pct", "Proporción de pérdida máxima", "Highest miss rate", 2, 5, False, "≤ 2 %"),
            ("max_false_alarm_rate_pct", "Proporción de falsa alarma máxima", "Highest false alarm rate", 5, 10, False, "≤ 5 %")):
        v = m.get(key)
        if v is None:
            continue
        lv = _band(v, good, marginal, hib)
        out.append(_item(lv, f"{es} = {_fmt(v)} % ({word[lv][0]}; aceptable {sym}).",
                         f"{en} = {_fmt(v)} % ({word[lv][1]}; acceptable {sym}).", table))
    k = m.get("min_kappa_vs_reference")
    if k is None:
        k = m.get("min_kappa_between_pairs")
    if k is not None:
        lv = "ok" if k > 0.75 else "bad" if k < 0.4 else "warn"
        out.append(_item(lv, f"Kappa mínimo = {k:.3f}: > 0.75 indica acuerdo bueno a excelente; < 0.4, acuerdo pobre.",
                         f"Lowest kappa = {k:.3f}: > 0.75 indicates good to excellent agreement; < 0.4, poor agreement.",
                         _ref("Cap. III, Secc. C, p. 137", "Ch. III, Sec. C, p. 137")))
    return out


_BY_METHOD = {
    "GRR_CROSSED_AR": _grr, "GRR_CROSSED_ANOVA": _grr, "GRR_NESTED_ANOVA": _grr,
    "BIAS": _bias, "LINEARITY": _linearity, "STABILITY": _stability,
    "ATTRIBUTE_AGREEMENT": _attribute,
}


def guidance(method: str, results: dict) -> list[dict]:
    fn = _BY_METHOD.get(method)
    return fn(results.get("metrics") or {}) if fn else []
