"""Demo instance with FICTITIOUS data, loaded through the public API (all business rules apply).

Run only against the dedicated demo database (see scripts/demo-reset.ps1):

    DATABASE_URL=postgresql+psycopg://.../gagetracker_demo python -m scripts.seed_demo

Every name is marked [DEMO]. The MSA studies use the published AIAG reference datasets.
"""

import os
import sys
from datetime import date, timedelta

from fastapi.testclient import TestClient
from fpdf import FPDF

if "demo" not in os.environ.get("DATABASE_URL", ""):
    sys.exit("Refusing to seed: DATABASE_URL must point to a database whose name contains 'demo'.")

from app.main import create_app  # noqa: E402
from tests.msa_reference import BIAS_AIAG, grr_observations, linearity_observations  # noqa: E402

PASSWORD = os.environ.get("DEMO_PASSWORD", "Demo-GageTracker-2026")
DOMAIN = "demo.example.com"   # reserved example domain: never a real mailbox
TODAY = date.today()
c = TestClient(create_app())


def iso(days=0):
    return (TODAY + timedelta(days=days)).isoformat()


def pdf_bytes(title: str) -> bytes:
    p = FPDF()
    p.add_page()
    p.set_font("Helvetica", "B", 14)
    p.cell(0, 10, title.encode("latin-1", "replace").decode("latin-1"))
    p.ln(12)
    p.set_font("Helvetica", "", 10)
    p.multi_cell(0, 6, "DEMO DOCUMENT - fictitious data for demonstration purposes only.")
    return bytes(p.output())


class Actor:
    def __init__(self, token, org):
        self.h = {"Authorization": f"Bearer {token}", "X-Organization-Id": org}

    def __call__(self, method, path, body=None, ok=(200, 201, 204), **kw):
        r = c.request(method, f"/api/v1{path}", json=body, headers=self.h, **kw)
        if r.status_code not in ok:
            raise RuntimeError(f"{method} {path} -> {r.status_code} {r.text[:400]}")
        return r.json() if r.content and r.headers.get("content-type", "").startswith("application/json") else None


def login(email):
    return c.post("/api/v1/auth/login", json={"email": email, "password": PASSWORD}).json()["access_token"]


def main():
    r = c.post("/api/v1/auth/register", json={
        "organization_name": "[DEMO] Autopartes Demostración S.A.", "plant_code": "MTY",
        "plant_name": "[DEMO] Planta Monterrey", "timezone": "America/Monterrey", "full_name": "[DEMO] Ana Admin",
        "email": f"admin@{DOMAIN}", "password": PASSWORD})
    if r.status_code == 409:
        sys.exit("The demo organization already exists: run scripts/demo-reset.ps1 to rebuild the demo database.")
    if r.status_code != 201:
        sys.exit(f"register failed: {r.text}")
    token = r.json()["access_token"]
    org = c.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"}).json()["memberships"][0]["organization_id"]
    A = Actor(token, org)
    mty = A("GET", "/plants")[0]["id"]
    slp = A("POST", "/plants", {"code": "SLP", "name": "[DEMO] Planta San Luis Potosí"})["id"]
    qa = A("POST", "/departments", {"plant_id": mty, "code": "QA", "name": "[DEMO] Calidad"})["id"]
    A("POST", "/departments", {"plant_id": mty, "code": "PRD", "name": "[DEMO] Producción"})

    people = {}
    for role, name in (("metrology_manager", "Mario Metrología"), ("metrology_manager", "Paula Aprobadora"),
                       ("metrology_technician", "Tomás Técnico"), ("lab_technician", "Laura Laboratorio"),
                       ("requester", "Sergio Solicitante"), ("auditor", "Aurora Auditora"), ("viewer", "Víctor Consulta")):
        email = f"{name.split()[0].lower()}@{DOMAIN}"
        u = A("POST", "/users", {"email": email, "full_name": f"[DEMO] {name}", "password": PASSWORD,
                                 "role_code": role, "plant_ids": []})
        people[name.split()[0].lower()] = (u["id"], email)
    uid = {k: v[0] for k, v in people.items()}
    me = A("GET", "/auth/me")["id"]
    for user, acts in ((uid["tomás"], ["INTERNAL_CALIBRATION", "ROUTINE_VERIFICATION", "MSA_EVALUATION"]),
                       (uid["mario"], ["TECHNICAL_REVIEW", "MSA_EVALUATION"]), (uid["paula"], ["APPROVAL"]),
                       (uid["laura"], ["LAB_SERVICE", "DIMENSIONAL_INSPECTION"]), (me, ["MSA_EVALUATION"])):
        for act in acts:
            A("POST", "/competency/authorizations", {"user_id": user, "activity": act, "valid_from": iso(-120),
                                                     "valid_until": iso(25) if act == "ROUTINE_VERIFICATION" else None})

    types = {code: A("POST", "/gage-types", {"code": code, "name": name, "default_frequency_days": f})["id"]
             for code, name, f in (("CAL", "Calibrador vernier digital", 365), ("MIC", "Micrómetro exterior", 365),
                                   ("IND", "Indicador de carátula", 180), ("TOR", "Torquímetro", 180),
                                   ("PIN", "Calibre pasa/no pasa", 365))}
    gages = {}
    specs = [("DEMO-CAL-001", "CAL", mty, -20, "HIGH"), ("DEMO-CAL-002", "CAL", mty, -340, "MEDIUM"),
             ("DEMO-CAL-003", "CAL", slp, -400, "LOW"), ("DEMO-MIC-001", "MIC", mty, -60, "HIGH"),
             ("DEMO-MIC-002", "MIC", mty, -120, "HIGH"), ("DEMO-IND-001", "IND", mty, -170, "MEDIUM"),
             ("DEMO-IND-002", "IND", slp, -30, "MEDIUM"), ("DEMO-TOR-001", "TOR", slp, -200, "HIGH"),
             ("DEMO-PIN-001", "PIN", mty, -90, "LOW"), ("DEMO-PIN-002", "PIN", mty, -10, "LOW")]
    for code, t, plant, last, crit in specs:
        g = A("POST", "/gages", {"gage_code": code, "description": f"[DEMO] {code}", "gage_type_id": types[t],
                                 "plant_id": plant, "department_id": qa if plant == mty else None,
                                 "manufacturer": "Demo Instruments", "serial_number": f"SN-{code[-3:]}",
                                 "criticality": crit, "last_calibration_date": iso(last), "location": "[DEMO] Lab 1",
                                 "responsible_user_id": uid["mario"]})
        gages[code] = g["id"]
    A("POST", f"/gages/{gages['DEMO-PIN-002']}/transitions", {"target": "OUT_OF_SERVICE", "reason": "[DEMO] Desgaste"})

    std = A("POST", "/standards", {"standard_code": "DEMO-STD-GB01", "description": "[DEMO] Juego de bloques patrón",
                                   "category": "GAUGE_BLOCK", "plant_id": mty, "calibration_frequency_days": 365})
    c.post(f"/api/v1/standards/{std['id']}/certificates", headers=A.h,
           data={"certificate_number": "DEMO-CERT-001", "issuer": "[DEMO] Laboratorio Acreditado",
                 "calibration_date": iso(-60), "issue_date": iso(-58), "traceability": "[DEMO] Patrón nacional"},
           files={"file": ("demo-cert.pdf", pdf_bytes("[DEMO] Certificado de patron"), "application/pdf")})

    T, M, P = (Actor(login(people[k][1]), org) for k in ("tomás", "mario", "paula"))

    def calibrate(gage, performed, found, left=None):
        act = A("POST", "/calibrations", {"gage_id": gages[gage], "activity_type": "INTERNAL_CALIBRATION",
                                          "planned_date": iso(performed)})
        aid = act["id"]
        A("POST", f"/calibrations/{aid}/request", {})
        A("POST", f"/calibrations/{aid}/schedule", {"scheduled_date": iso(performed), "technician_id": uid["tomás"]})
        T("POST", f"/calibrations/{aid}/start")
        T("PATCH", f"/calibrations/{aid}", {"performed_date": iso(performed), "method": "[DEMO] PR-MET-04",
                                            "environment_temperature": "20.1", "environment_humidity": "45",
                                            "adjusted": left is not None})
        for phase, v in (("AS_FOUND", found), ("AS_LEFT", left)):
            if v:
                T("POST", f"/calibrations/{aid}/points", {"phase": phase, "nominal": "10", "lower_limit": "9.98",
                                                          "upper_limit": "10.02", "measured": v, "unit": "mm",
                                                          "description": "Bloque 10 mm"})
        T("POST", f"/calibrations/{aid}/standards", {"standard_id": std["id"]})
        T("POST", f"/calibrations/{aid}/submit", {})
        M("POST", f"/calibrations/{aid}/review", {"accept": True, "comments": "[DEMO] Revisión técnica OK"})
        P("POST", f"/calibrations/{aid}/approve", {"accept": True})
        return A("POST", f"/calibrations/{aid}/release", {})

    calibrate("DEMO-MIC-001", -30, "10.005")
    A("POST", "/calibrations", {"gage_id": gages["DEMO-CAL-002"], "activity_type": "INTERNAL_CALIBRATION",
                                "planned_date": iso(10)})

    # Laboratory: request -> work order -> measurements -> report.
    L = Actor(login(people["laura"][1]), org)
    svc = A("POST", "/lab/services", {"code": "DIM", "name": "[DEMO] Inspección dimensional", "standard_hours": "2"})
    req = Actor(login(people["sergio"][1]), org)("POST", "/lab/requests", {
        "plant_id": mty, "service_id": svc["id"], "part_number": "DEMO-PN-4471", "part_revision": "C",
        "description": "[DEMO] Primera pieza", "priority": "HIGH", "requested_date": iso(3),
        "customer_type": "EXTERNAL", "customer_name": "[DEMO] Cliente Automotriz"})
    A("POST", f"/lab/requests/{req['id']}/decision", {"approve": True, "committed_date": iso(5)})
    wo = A("POST", "/lab/work-orders", {"service_request_id": req["id"]})
    A("POST", f"/lab/work-orders/{wo['id']}/schedule", {"technician_id": uid["laura"],
                                                        "scheduled_start": f"{iso(0)}T15:00:00Z",
                                                        "scheduled_end": f"{iso(0)}T17:00:00Z",
                                                        "gage_ids": [gages["DEMO-MIC-001"]]})
    L("POST", f"/lab/work-orders/{wo['id']}/start")
    for n, (char, nom, lo, hi, meas) in enumerate((("Diámetro de barreno", "10", "9.95", "10.05", "10.01"),
                                                   ("Longitud total", "25", "24.9", "25.1", "25.04")), start=1):
        L("POST", f"/lab/work-orders/{wo['id']}/results", {
            "part_number": "DEMO-PN-4471", "drawing_revision": "C", "sample_id": "1", "characteristic_number": str(n),
            "characteristic": char, "nominal": nom, "lower_limit": lo, "upper_limit": hi, "measured": meas,
            "unit": "mm", "gage_id": gages["DEMO-MIC-001"]})
    L("POST", f"/lab/work-orders/{wo['id']}/complete", {})
    M("POST", f"/lab/work-orders/{wo['id']}/reports", {})   # issued by an authorized technical reviewer

    # MSA: acceptance criteria (author: admin, approver: Paula) and studies with reference datasets.
    for tpl in A("GET", "/msa/criteria/templates"):
        for method in tpl["methods"]:
            crit = A("POST", "/msa/criteria", {"name": f"[DEMO] {tpl['name']} · {method}", "method": method,
                                               "scope": "ORGANIZATION", "rules": tpl["rules"], "source": tpl["source"]})
            P("POST", f"/msa/criteria/{crit['id']}/approve")

    def study(title, method, gage, design, rows):
        s = A("POST", "/msa/studies", {"title": f"[DEMO] {title}", "method": method, "characteristic": title,
                                       "part_number": "DEMO-PN-4471", "plant_id": mty, "gage_id": gages[gage],
                                       "responsible_id": me, "start_date": iso(-5), "design": design})
        A("POST", f"/msa/studies/{s['id']}/observations", {"observations": rows})
        A("POST", f"/msa/studies/{s['id']}/calculate")
        return s

    grr = study("GRR diámetro (Promedio y Rango, datos AIAG)", "GRR_CROSSED_AR", "DEMO-MIC-002",
                {"operators": 3, "parts": 10, "trials": 3, "tolerance": 4.0}, grr_observations())
    study("GRR diámetro (ANOVA, datos AIAG)", "GRR_CROSSED_ANOVA", "DEMO-MIC-002",
          {"operators": 3, "parts": 10, "trials": 3, "tolerance": 4.0}, grr_observations())
    study("Sesgo (datos AIAG)", "BIAS", "DEMO-CAL-001", {"reference": BIAS_AIAG["reference"]},
          [{"trial": i + 1, "value": v} for i, v in enumerate(BIAS_AIAG["values"])])
    study("Linealidad (datos AIAG)", "LINEARITY", "DEMO-CAL-001", {}, linearity_observations())
    A("POST", f"/workflows/msa_study/{grr['id']}/transitions", {"transition": "SUBMIT"})
    P("POST", f"/msa/studies/{grr['id']}/conclusion", {"decision": "CONDITIONAL",
                                                       "comment": "[DEMO] Uso limitado a inspección final"})
    P("POST", f"/workflows/msa_study/{grr['id']}/transitions", {"transition": "APPROVE"})
    A("POST", f"/msa/studies/{grr['id']}/reports", {"lang": "es"})

    # OOT: an As Found out of tolerance opens a case automatically and restricts the gage.
    calibrate("DEMO-MIC-001", 0, "10.05", left="10.00")
    case = A("GET", f"/oot/cases?gage_id={gages['DEMO-MIC-001']}")[0]
    A("POST", f"/workflows/oot_case/{case['id']}/transitions", {"transition": "INVESTIGATE"})
    A("POST", f"/oot/cases/{case['id']}/analysis")
    A("POST", f"/oot/cases/{case['id']}/items", {"ref_code": "[DEMO] LOTE-2291", "description": "[DEMO] Lote enviado"})
    print(f"Demo ready. Organization: [DEMO] Autopartes Demostración S.A. Users @{DOMAIN}; password from DEMO_PASSWORD.")


if __name__ == "__main__":
    main()
