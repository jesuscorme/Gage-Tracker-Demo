"""PDF rendering of an issued measurement report (from its frozen snapshot)."""

from fpdf import FPDF


def _t(v) -> str:
    """Core PDF fonts are Latin-1: keep accents and ±, replace anything else."""
    return ("" if v is None else str(v)).encode("latin-1", "replace").decode("latin-1")


class _Report(FPDF):
    def __init__(self, snap: dict):
        super().__init__(orientation="L", unit="mm", format="A4")
        self.snap = snap
        self.set_auto_page_break(auto=True, margin=15)
        self.set_title(_t(f"{snap['report_code']} rev {snap['revision']}"))

    def header(self):
        s = self.snap
        self.set_font("Helvetica", "B", 14)
        self.cell(0, 8, _t("Measurement Report / Reporte de medición"), new_x="LMARGIN", new_y="NEXT")
        self.set_font("Helvetica", "", 9)
        self.cell(0, 5, _t(f"{s['organization']}   ·   {s['report_code']}  rev {s['revision']}   ·   "
                           f"Issued {s['issued_on']}"), new_x="LMARGIN", new_y="NEXT")
        self.ln(2)

    def footer(self):
        self.set_y(-12)
        self.set_font("Helvetica", "", 8)
        self.cell(0, 5, _t(f"Gage Tracker · {self.snap['report_code']} rev {self.snap['revision']} · page {self.page_no()}"),
                  align="R")


def render_report(snap: dict) -> bytes:
    pdf = _Report(snap)
    pdf.add_page()
    pdf.set_font("Helvetica", "", 9)
    info = [
        ("Customer", f"{snap.get('customer') or '-'} ({snap['customer_type']})"),
        ("Request / Work order", f"{snap['request']} / {snap['work_order']}"),
        ("Service", snap["service"]),
        ("Part number / revision", f"{snap.get('part_number') or '-'} / {snap.get('part_revision') or '-'}"),
        ("Technician / Reviewer", f"{snap.get('technician') or '-'} / {snap.get('reviewer') or '-'}"),
        ("Equipment", ", ".join(snap.get("equipment") or []) or "-"),
    ]
    for label, value in info:
        pdf.set_font("Helvetica", "B", 9)
        pdf.cell(50, 5, _t(label))
        pdf.set_font("Helvetica", "", 9)
        pdf.cell(0, 5, _t(value), new_x="LMARGIN", new_y="NEXT")
    pdf.ln(2)
    pdf.set_font("Helvetica", "B", 11)
    pdf.cell(0, 7, _t(f"Acceptance: {snap['acceptance']}"), new_x="LMARGIN", new_y="NEXT")
    pdf.ln(1)

    cols = [("Part", 30), ("Rev", 12), ("Sample", 16), ("No.", 14), ("Characteristic", 62), ("Nominal", 24),
            ("Lower", 24), ("Upper", 24), ("Measured", 24), ("Unit", 14), ("Gage", 22), ("Result", 14)]
    pdf.set_font("Helvetica", "B", 8)
    pdf.set_fill_color(235, 238, 242)
    for name, w in cols:
        pdf.cell(w, 6, _t(name), border=1, fill=True)
    pdf.ln()
    pdf.set_font("Helvetica", "", 8)
    for r in snap["results"]:
        values = [r["part_number"], r.get("drawing_revision"), r.get("sample"), r["number"], r["characteristic"],
                  r["nominal"], r["lower"], r["upper"], r["measured"], r["unit"], r.get("gage"), r["result"]]
        for (name, w), v in zip(cols, values):
            if name == "Result" and v == "NOK":
                pdf.set_text_color(180, 30, 40)
            pdf.cell(w, 5.5, _t(v)[: int(w / 1.6)], border=1)
            pdf.set_text_color(0, 0, 0)
        pdf.ln()
    if snap.get("observations"):
        pdf.ln(3)
        pdf.set_font("Helvetica", "B", 9)
        pdf.cell(0, 5, "Observations", new_x="LMARGIN", new_y="NEXT")
        pdf.set_font("Helvetica", "", 9)
        pdf.multi_cell(0, 5, _t(snap["observations"]))
    if snap.get("revision_reason"):
        pdf.ln(2)
        pdf.set_font("Helvetica", "I", 8)
        pdf.multi_cell(0, 4, _t(f"Revision reason: {snap['revision_reason']}"))
    return bytes(pdf.output())
