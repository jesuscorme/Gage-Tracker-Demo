"""PDF report of an MSA study, rendered from a frozen snapshot of one run.

Charts are drawn with PDF primitives (lines, rectangles), so the report depends only on
the stored numbers and never on the current state of the study.
"""

from fpdf import FPDF

METHOD_NAMES = {
    "GRR_CROSSED_AR": "Gage R&R crossed - Average & Range",
    "GRR_CROSSED_ANOVA": "Gage R&R crossed - ANOVA",
    "GRR_NESTED_ANOVA": "Gage R&R nested - ANOVA",
    "ATTRIBUTE_AGREEMENT": "Attribute Agreement Analysis",
    "BIAS": "Bias study",
    "LINEARITY": "Linearity study",
    "STABILITY": "Stability study",
    "TYPE1": "Type 1 gage study",
}


ES = {'MSA Study Report': 'Reporte de estudio MSA', 'run': 'cálculo', 'issued': 'emitido', 'page': 'página', 'Statistical results': 'Resultados estadísticos', 'Model': 'Modelo', 'Source': 'Fuente', 'StdDev': 'Desv. est.', 'Variance': 'Varianza', 'Study var': 'Var. estudio', '%Contribution': '%Contribución', '%Study var': '%Var. estudio', '%Tolerance': '%Tolerancia', 'Study variation multiplier': 'Multiplicador de variación de estudio', 'Components of variation (%Study variation)': 'Componentes de variación (%Var. estudio)', 'Range chart by operator': 'Carta de rangos por operador', 'Average chart by operator': 'Carta de promedios por operador', 'Appraiser': 'Evaluador', 'Within %': 'Dentro %', 'vs reference %': 'vs referencia %', 'kappa vs ref': 'kappa vs ref.', 'Effectiveness %': 'Efectividad %', 'Miss %': 'Omisión %', 'False alarm %': 'Falsa alarma %', 'Between appraisers': 'Entre evaluadores', 'All vs reference': 'Todos vs referencia', 'Within-appraiser agreement (%)': 'Acuerdo dentro del evaluador (%)', '95% CI of bias': 'IC 95 % del sesgo', 'CI of bias': 'IC del sesgo', 'Histogram of readings': 'Histograma de lecturas', 'Readings vs reference': 'Lecturas vs referencia', 'Run chart (reference +/- K/2 % of tolerance)': 'Gráfica de corrida (referencia +/- K/2 % de la tolerancia)', 'Part': 'Pieza', 'Reference': 'Referencia', 'Average bias': 'Sesgo promedio', 'Bias vs reference (points), fit and confidence bands': 'Sesgo vs referencia (puntos), ajuste y bandas de confianza', 'Fitted line and confidence bands by reference value': 'Recta ajustada y bandas de confianza por valor de referencia', 'Subgroup': 'Subgrupo', 'Criterion': 'Criterio', 'Note': 'Nota', 'Study': 'Estudio', 'Title': 'Título', 'Characteristic': 'Característica', 'Part number / revision': 'Número de parte / revisión', 'Customer': 'Cliente', 'Plant / department': 'Planta / departamento', 'Gage': 'Instrumento', 'status at calculation': 'estado al calcular', 'next due': 'vence', 'Responsible': 'Responsable', 'Dates': 'Fechas', 'start': 'inicio', 'end': 'fin', 'Operators / appraisers': 'Operadores / evaluadores', 'Design and method': 'Diseño y método', 'Method': 'Método', 'Design': 'Diseño', 'Parameters': 'Parámetros', 'defaults': 'predeterminados', 'Observations used': 'Observaciones utilizadas', 'Calculated': 'Calculado', 'by': 'por', 'Acceptance criteria and conclusion': 'Criterios de aceptación y conclusión', 'Interpretation': 'Interpretación', 'GUIDANCE_NOTE': 'Guía de interpretación (no sustituye a los criterios aprobados).', 'Criteria': 'Criterios', 'Approved': 'Aprobado', 'Metric': 'Indicador', 'Rule': 'Regla', 'Actual': 'Valor', 'Status': 'Estado', 'Computed decision': 'Decisión calculada', 'Conclusion': 'Conclusión', 'pending review': 'pendiente de revisión', 'Concluded by': 'Concluyó', 'Data': 'Datos', 'NO_CRITERIA_TEXT': 'No se aplicaron criterios de aceptación aprobados: el resultado es solo estadístico y no constituye una decisión de aceptación.', 'DISCLAIMER_TEXT': 'Este reporte documenta un análisis estadístico. La aceptación depende de los criterios aprobados por la organización y de su propia evaluación de los requisitos aplicables.', 'Gage R&R crossed - Average & Range': 'GRR cruzado - Promedio y Rango', 'Gage R&R crossed - ANOVA': 'GRR cruzado - ANOVA', 'Gage R&R nested - ANOVA': 'GRR anidado - ANOVA', 'Attribute Agreement Analysis': 'Análisis de concordancia por atributos', 'Bias study': 'Estudio de sesgo', 'Linearity study': 'Estudio de linealidad', 'Stability study': 'Estudio de estabilidad', 'Type 1 gage study': 'Estudio tipo 1'}
EN_LONG = {'GUIDANCE_NOTE': 'Interpretation guidance (does not replace the approved criteria).', 'NO_CRITERIA_TEXT': 'No approved acceptance criteria applied: the result is statistical only and does not constitute an acceptance decision.', 'DISCLAIMER_TEXT': 'This report documents a statistical analysis. Acceptance depends on the criteria approved by the organization and on its own evaluation of applicable requirements.'}


def _t(v) -> str:
    return ("" if v is None else str(v)).encode("latin-1", "replace").decode("latin-1")


def fmt(v, digits=4) -> str:
    if v is None:
        return "-"
    if isinstance(v, bool):
        return "yes" if v else "no"
    if isinstance(v, float):
        return f"{v:.{digits}f}"
    return str(v)


class _Pdf(FPDF):
    def __init__(self, snap: dict):
        super().__init__(orientation="P", unit="mm", format="A4")
        self.snap = snap
        self.lang = snap.get("lang", "en")
        self.set_auto_page_break(auto=True, margin=15)
        self.set_title(_t(f"{snap['study_code']} report rev {snap['revision']}"))

    def L(self, text: str) -> str:
        """Translate a fixed label (never data) to the report language."""
        if self.lang == "es":
            return ES.get(text, text)
        return EN_LONG.get(text, text)

    def header(self):
        s = self.snap
        self.set_font("Helvetica", "B", 13)
        self.cell(0, 7, _t(f"{self.L('MSA Study Report')} - {self.L(METHOD_NAMES.get(s['method'], s['method']))}"),
                  new_x="LMARGIN", new_y="NEXT")
        self.set_font("Helvetica", "", 8)
        self.cell(0, 4, _t(f"{s['organization']}  |  {s['study_code']} rev {s['revision']}  |  "
                           f"{self.L('run')} #{s['run_number']}  |  {self.L('issued')} {s['issued_on']}"), new_x="LMARGIN", new_y="NEXT")
        self.ln(2)

    def footer(self):
        s = self.snap
        self.set_y(-12)
        self.set_font("Helvetica", "", 7)
        self.cell(0, 4, _t(f"Gage Tracker MSA engine {s['engine_version']} / {s['method']} {s['algorithm_version']} "
                           f"({s['validation_status']}) | input sha256 {s['input_hash'][:16]}... | {self.L('page')} "
                           f"{self.page_no()}"), align="R")

    def section(self, title):
        self.ln(2)
        self.set_font("Helvetica", "B", 10)
        self.set_fill_color(235, 238, 242)
        self.cell(0, 6, _t(self.L(title)), fill=True, new_x="LMARGIN", new_y="NEXT")
        self.set_font("Helvetica", "", 8)
        self.ln(1)

    def kv(self, rows, col=48):
        for label, value in rows:
            self.set_font("Helvetica", "B", 8)
            self.cell(col, 4.5, _t(self.L(label)))
            self.set_font("Helvetica", "", 8)
            self.multi_cell(0, 4.5, _t(value), new_x="LMARGIN", new_y="NEXT")

    def table(self, header, rows, widths):
        self.set_font("Helvetica", "B", 7.5)
        for h, w in zip(header, widths):
            self.cell(w, 5, _t(self.L(h)), border=1, fill=True)
        self.ln()
        self.set_font("Helvetica", "", 7.5)
        for r in rows:
            if self.get_y() > 270:
                self.add_page()
            for v, w in zip(r, widths):
                self.cell(w, 4.5, _t(v)[: int(w / 1.5)], border=1)
            self.ln()

    # -------------------------------------------------------------- charts

    def _frame(self, x, y, w, h, title, lo, hi):
        self.set_draw_color(160, 160, 160)
        self.rect(x, y, w, h)
        self.set_font("Helvetica", "B", 7)
        self.set_xy(x, y - 4)
        self.cell(w, 4, _t(self.L(title)))
        self.set_font("Helvetica", "", 6)
        self.set_xy(x - 14, y - 1.5)
        self.cell(13, 3, _t(fmt(hi, 3)), align="R")
        self.set_xy(x - 14, y + h - 1.5)
        self.cell(13, 3, _t(fmt(lo, 3)), align="R")

    def line_chart(self, title, series, hlines=(), height=38, points_only=False):
        vals = [v for s in series for v in s["values"] if v is not None] + [v for v, _ in hlines if v is not None]
        if not vals:
            return
        lo, hi = min(vals), max(vals)
        if hi == lo:
            hi, lo = hi + 1, lo - 1
        pad = (hi - lo) * 0.08
        lo, hi = lo - pad, hi + pad
        if self.get_y() + height + 12 > 280:
            self.add_page()
        x, y, w, h = self.l_margin + 16, self.get_y() + 6, 170, height
        self._frame(x, y, w, h, title, lo, hi)
        n = max(len(s["values"]) for s in series)
        sx = (lambda i: x + w * (i + 0.5) / n)
        sy = (lambda v: y + h - (v - lo) / (hi - lo) * h)
        for value, label in hlines:
            if value is None:
                continue
            self.set_draw_color(200, 60, 60) if label in ("UCL", "LCL", "limit") else self.set_draw_color(80, 80, 80)
            self.set_dash_pattern(dash=1, gap=1)
            self.line(x, sy(value), x + w, sy(value))
            self.set_dash_pattern()
            self.set_font("Helvetica", "", 5.5)
            self.set_xy(x + w + 0.5, sy(value) - 1.5)
            self.cell(14, 3, _t(f"{label} {fmt(value, 3)}"))
        palette = [(31, 92, 153), (214, 110, 30), (40, 140, 80), (150, 60, 160), (120, 120, 120)]
        for k, s in enumerate(series):
            self.set_draw_color(*palette[k % len(palette)])
            self.set_fill_color(*palette[k % len(palette)])
            prev = None
            for i, v in enumerate(s["values"]):
                if v is None:
                    prev = None
                    continue
                px, py = sx(i), sy(v)
                if prev and not points_only:
                    self.line(prev[0], prev[1], px, py)
                self.ellipse(px - 0.6, py - 0.6, 1.2, 1.2, style="F")
                prev = (px, py)
        if len(series) > 1:
            self.set_font("Helvetica", "", 6)
            self.set_xy(x, y + h + 0.5)
            self.set_text_color(60, 60, 60)
            self.cell(w, 3, _t("  ".join(f"[{k + 1}] {s['label']}" for k, s in enumerate(series))))
            self.set_text_color(0, 0, 0)
        self.set_draw_color(0, 0, 0)
        self.set_y(y + h + 5)

    def bar_chart(self, title, labels, values, height=34, ref=None):
        clean = [v for v in values if v is not None]
        if not clean:
            return
        hi = max(clean + ([ref] if ref else [])) * 1.1 or 1
        if self.get_y() + height + 12 > 280:
            self.add_page()
        x, y, w, h = self.l_margin + 16, self.get_y() + 6, 170, height
        self._frame(x, y, w, h, title, 0, hi)
        bw = w / max(len(values), 1)
        self.set_fill_color(31, 92, 153)
        self.set_font("Helvetica", "", 6)
        for i, (lab, v) in enumerate(zip(labels, values)):
            if v is None:
                continue
            bh = v / hi * h
            self.rect(x + i * bw + bw * 0.15, y + h - bh, bw * 0.7, bh, style="F")
            self.set_xy(x + i * bw, y + h + 0.5)
            self.cell(bw, 3, _t(f"{lab} {fmt(v, 1)}"), align="C")
        if ref:
            self.set_draw_color(200, 60, 60)
            self.line(x, y + h - ref / hi * h, x + w, y + h - ref / hi * h)
            self.set_draw_color(0, 0, 0)
        self.set_y(y + h + 6)


def _results(pdf: _Pdf, snap: dict) -> None:
    r = snap["results"]
    m = r["metrics"]
    fam = snap["family"]
    pdf.section("Statistical results")
    pdf.kv([("Model", r.get("model"))])
    if fam == "VARIABLE_GRR":
        rows = [[c["source"], fmt(c["sd"], 5), fmt(c["variance"], 6), fmt(c["study_var"], 5),
                 fmt(c["pct_contribution"], 2), fmt(c["pct_study_var"], 2), fmt(c["pct_tolerance"], 2)]
                for c in r["tables"]["components"]]
        pdf.table(["Source", "StdDev", "Variance", "Study var", "%Contribution", "%Study var", "%Tolerance"], rows,
                  [32, 22, 24, 24, 26, 24, 24])
        pdf.kv([("ndc", fmt(m.get("ndc"))), ("Study variation multiplier", fmt(r["design"].get("study_var_multiplier")))])
        if r["tables"].get("anova"):
            pdf.ln(1)
            pdf.table(["Source", "DF", "SS", "MS", "F", "p"],
                      [[a["source"], a["df"], fmt(a["ss"], 5), fmt(a["ms"], 5), fmt(a["f"], 3), fmt(a["p"], 4)]
                       for a in r["tables"]["anova"]], [40, 15, 32, 32, 25, 25])
        comps = [c for c in r["tables"]["components"] if c["source"] in ("EV", "AV", "GRR", "PV")]
        pdf.bar_chart("Components of variation (%Study variation)", [c["source"] for c in comps],
                      [c["pct_study_var"] for c in comps])
        ch = r["charts"]
        if "range_chart" in ch:
            rc = ch["range_chart"]
            pdf.line_chart("Range chart by operator", [{"label": op, "values": rc["values"][i]}
                                                       for i, op in enumerate(rc["operators"])],
                           [(rc["center"], "R-bar"), (rc["ucl"], "UCL")])
            ac = ch["average_chart"]
            pdf.line_chart("Average chart by operator", [{"label": op, "values": ac["values"][i]}
                                                         for i, op in enumerate(ac["operators"])],
                           [(ac["center"], "mean"), (ac["ucl"], "UCL"), (ac["lcl"], "LCL")])
    elif fam == "ATTRIBUTE":
        t = r["tables"]
        pdf.table(["Appraiser", "Within %", "vs reference %", "kappa vs ref", "Effectiveness %", "Miss %",
                   "False alarm %"],
                  [[w["operator"], fmt(w.get("pct"), 1),
                    fmt(next((v["pct"] for v in t["vs_reference"] if v["operator"] == w["operator"]), None), 1),
                    fmt(next((v["cohen_kappa"] for v in t["vs_reference_kappa"] if v["operator"] == w["operator"]),
                             None), 3),
                    fmt(next((e["effectiveness_pct"] for e in t["effectiveness"] if e["operator"] == w["operator"]),
                             None), 1),
                    fmt(next((e["miss_rate_pct"] for e in t["effectiveness"] if e["operator"] == w["operator"]),
                             None), 1),
                    fmt(next((e["false_alarm_rate_pct"] for e in t["effectiveness"]
                              if e["operator"] == w["operator"]), None), 1)] for w in t["within"]],
                  [28, 22, 26, 24, 28, 20, 26])
        if t.get("between"):
            pdf.kv([("Between appraisers", f"{fmt(t['between']['pct'], 1)} % (Fleiss kappa "
                                           f"{fmt(t['between'].get('fleiss_kappa'), 3)})"),
                    ("All vs reference", fmt(t["all_vs_reference"]["pct"], 1) if t.get("all_vs_reference") else "-")])
        for pk in t.get("pair_kappa", []):
            pdf.kv([(f"Cohen kappa {pk['pair']}", fmt(pk["cohen_kappa"], 3))])
        pdf.bar_chart("Within-appraiser agreement (%)", [w["operator"] for w in t["within"]],
                      [w.get("pct") for w in t["within"]])
    else:
        summary = r["tables"].get("summary") or r["tables"].get("regression") or {}
        pdf.kv([(k, fmt(v, 5)) for k, v in m.items()])
        if summary and fam in ("BIAS", "TYPE1"):
            pdf.kv([("95% CI of bias" if fam == "BIAS" else "CI of bias",
                     f"[{fmt(summary.get('ci_low'), 5)}, {fmt(summary.get('ci_high'), 5)}]")])
        ch = r["charts"]
        if fam == "BIAS":
            pdf.bar_chart("Histogram of readings", [fmt(e, 3) for e in ch["histogram"]["edges"][:-1]],
                          ch["histogram"]["counts"])
            pdf.line_chart("Readings vs reference", [{"label": "reading", "values": ch["values"]}],
                           [(ch["reference"], "ref")])
        elif fam == "TYPE1":
            run = ch["run"]
            pdf.line_chart("Run chart (reference +/- K/2 % of tolerance)", [{"label": "reading",
                                                                              "values": run["values"]}],
                           [(run["reference"], "ref"), (run["upper"], "limit"), (run["lower"], "limit")])
        elif fam == "LINEARITY":
            pts = ch["points"]
            pdf.table(["Part", "Reference", "n", "Average bias"],
                      [[p["part"], fmt(p["reference"], 4), p["n"], fmt(p["average_bias"], 5)]
                       for p in r["tables"]["per_part"]], [30, 30, 15, 35])
            pdf.line_chart("Bias vs reference (points), fit and confidence bands",
                           [{"label": "bias", "values": [p["bias"] for p in pts]}], [(0.0, "bias=0")],
                           points_only=True)
            bands = ch["bands"]
            pdf.line_chart("Fitted line and confidence bands by reference value",
                           [{"label": "fit", "values": [b["fit"] for b in bands]},
                            {"label": "lower", "values": [b["lower"] for b in bands]},
                            {"label": "upper", "values": [b["upper"] for b in bands]}], [(0.0, "bias=0")])
        elif fam == "STABILITY":
            loc, disp = ch["location"], ch["dispersion"]
            pdf.line_chart(f"{loc['kind']} chart", [{"label": loc["kind"], "values": loc["values"]}],
                           [(loc["center"], "CL"), (loc["ucl"], "UCL"), (loc["lcl"], "LCL"),
                            (loc.get("reference"), "ref")])
            pdf.line_chart(f"{disp['kind']} chart", [{"label": disp["kind"], "values": disp["values"]}],
                           [(disp["center"], "CL"), (disp["ucl"], "UCL")])
            if r["tables"]["violations"]:
                pdf.table(["Subgroup", "Criterion"],
                          [[v["subgroup"], v["rule"]] for v in r["tables"]["violations"]], [30, 60])
    for w in r.get("warnings") or []:
        pdf.set_font("Helvetica", "I", 7.5)
        pdf.multi_cell(0, 4, _t(f"{pdf.L('Note')}: {w}"), new_x="LMARGIN", new_y="NEXT")


GUIDANCE_TAG = {"ok": "OK", "warn": "!", "bad": "X", "info": "i"}


def _guidance(pdf: _Pdf, items: list[dict]) -> None:
    if not items:
        return
    pdf.section("Interpretation")
    pdf.set_font("Helvetica", "I", 7.5)
    pdf.multi_cell(0, 4, _t(pdf.L("GUIDANCE_NOTE")), new_x="LMARGIN", new_y="NEXT")
    lang = "es" if pdf.lang == "es" else "en"
    for g in items:
        text = g[lang].replace("≥", ">=").replace("≤", "<=")
        pdf.set_font("Helvetica", "B", 8.5)
        pdf.cell(8, 4.5, GUIDANCE_TAG.get(g["level"], ""))
        pdf.set_font("Helvetica", "", 8.5)
        pdf.multi_cell(0, 4.5, _t(text), new_x="LMARGIN", new_y="NEXT")
        pdf.ln(1)


def render(snap: dict) -> bytes:
    pdf = _Pdf(snap)
    pdf.add_page()
    pdf.section("Study")
    pdf.kv([
        ("Title", snap["title"]), ("Characteristic", snap["characteristic"]),
        ("Part number / revision", f"{snap.get('part_number') or '-'} / {snap.get('part_revision') or '-'}"),
        ("Customer", snap.get("customer") or "-"),
        ("Plant / department", f"{snap['plant']} / {snap.get('department') or '-'}"),
        ("Gage", f"{snap['gage']['gage_code']} - {snap['gage']['description']} ({pdf.L('status at calculation')}: "
                 f"{snap['gage']['status']}; {pdf.L('next due')} {snap['gage'].get('next_due_date') or '-'})"),
        ("Responsible", snap["responsible"]),
        ("Dates", f"{pdf.L('start')} {snap['start_date']}  {pdf.L('end')} {snap.get('end_date') or '-'}"),
        ("Operators / appraisers", ", ".join(snap.get("operators") or []) or "-"),
    ])
    pdf.section("Design and method")
    d = snap["input"]["design"]
    pdf.kv([("Method", f"{pdf.L(METHOD_NAMES.get(snap['method'], snap['method']))} ({snap['method']})"),
            ("Design", ", ".join(f"{k}={v}" for k, v in d.items() if not isinstance(v, (dict, list))) or "-"),
            ("Parameters", ", ".join(f"{k}={v}" for k, v in snap["input"]["params"].items()) or pdf.L("defaults")),
            ("Observations used", str(len(snap["input"]["observations"]))),
            ("Calculated", f"{snap['calculated_at']} {pdf.L('by')} {snap['calculated_by']}")])
    _results(pdf, snap)
    _guidance(pdf, snap.get("guidance") or [])
    pdf.section("Acceptance criteria and conclusion")
    crit = snap.get("criteria")
    if crit:
        pdf.kv([("Criteria", f"{crit['name']} v{crit['version']} ({crit['scope']})"),
                ("Approved", f"{crit.get('approved_at') or '-'}")])
        pdf.table(["Metric", "Rule", "Actual", "Status"],
                  [[e["metric"], f"{e['op']} {e['value']}", fmt(e["actual"], 4), e["status"]]
                   for e in snap.get("evaluation") or []], [60, 40, 40, 40])
    else:
        pdf.kv([("Criteria", pdf.L("NO_CRITERIA_TEXT"))])
    pdf.kv([("Computed decision", snap["decision"]),
            ("Conclusion", f"{snap.get('final_decision') or pdf.L('pending review')}"
                           f"{' - ' + snap['final_comment'] if snap.get('final_comment') else ''}"),
            ("Concluded by", snap.get("concluded_by") or "-")])
    pdf.section("Data")
    obs = snap["input"]["observations"]
    keys = [k for k in ("operator", "part", "trial", "subgroup", "reference", "value", "measured_at")
            if any(k in o for o in obs)]
    widths = [max(18, int(180 / max(len(keys), 1)))] * len(keys)
    pdf.table(keys, [[fmt(o.get(k), 6) if isinstance(o.get(k), float) else o.get(k, "") for k in keys]
                     for o in obs], widths)
    pdf.ln(3)
    pdf.set_font("Helvetica", "I", 7)
    pdf.multi_cell(0, 3.5, _t(pdf.L("DISCLAIMER_TEXT")))
    return bytes(pdf.output())
