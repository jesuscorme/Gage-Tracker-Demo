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

    grr = study("GRR diámetro (Promedio y Rango)", "GRR_CROSSED_AR", "DEMO-MIC-002",
                {"operators": 3, "parts": 10, "trials": 3, "tolerance": 4.0}, grr_observations())
    study("GRR diámetro (ANOVA)", "GRR_CROSSED_ANOVA", "DEMO-MIC-002",
          {"operators": 3, "parts": 10, "trials": 3, "tolerance": 4.0}, grr_observations())
    study("Sesgo", "BIAS", "DEMO-CAL-001", {"reference": BIAS_AIAG["reference"]},
          [{"trial": i + 1, "value": v} for i, v in enumerate(BIAS_AIAG["values"])])
    study("Linealidad", "LINEARITY", "DEMO-CAL-001", {}, linearity_observations())
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

    extend(A, M, P, T, uid, people, org, gages, types, mty, slp, qa, svc, calibrate, study)
    print(f"Demo ready. Organization: [DEMO] Autopartes Demostración S.A. Users @{DOMAIN}; password from DEMO_PASSWORD.")


def extend(A, M, P, T, uid, people, org, gages, types, mty, slp, qa, svc, calibrate, study):
    """Volume and coverage so every screen of the application has something to show."""
    from tests.test_engine_grr import NESTED_HAND
    from tests.test_engine_other import TYPE1_VALUES, attribute_data

    # Gages: due soon, overdue, retired, transferred, out of service; both plants.
    more = [("DEMO-CAL-004", "CAL", mty, -350, "HIGH"), ("DEMO-CAL-005", "CAL", mty, -380, "MEDIUM"),
            ("DEMO-CAL-006", "CAL", slp, -100, "LOW"), ("DEMO-CAL-007", "CAL", slp, -358, "MEDIUM"),
            ("DEMO-MIC-003", "MIC", mty, -250, "HIGH"), ("DEMO-MIC-004", "MIC", slp, -370, "HIGH"),
            ("DEMO-MIC-005", "MIC", mty, -15, "MEDIUM"), ("DEMO-IND-003", "IND", mty, -175, "MEDIUM"),
            ("DEMO-IND-004", "IND", slp, -190, "LOW"), ("DEMO-IND-005", "IND", mty, -45, "HIGH"),
            ("DEMO-TOR-002", "TOR", mty, -160, "HIGH"), ("DEMO-TOR-003", "TOR", slp, -185, "MEDIUM"),
            ("DEMO-TOR-004", "TOR", mty, -20, "HIGH"), ("DEMO-PIN-003", "PIN", slp, -300, "LOW"),
            ("DEMO-PIN-004", "PIN", mty, -360, "LOW"), ("DEMO-PIN-005", "PIN", mty, -400, "MEDIUM")]
    owners = [uid["mario"], uid["tomás"], uid["laura"]]
    for n, (code, t, plant, last, crit) in enumerate(more):
        gages[code] = A("POST", "/gages", {
            "gage_code": code, "description": f"[DEMO] {code}", "gage_type_id": types[t], "plant_id": plant,
            "department_id": qa if plant == mty else None, "manufacturer": ("Demo Instruments", "Metro Demo")[n % 2],
            "serial_number": f"SN-{code[-7:]}", "criticality": crit, "last_calibration_date": iso(last),
            "location": f"[DEMO] Línea {n % 4 + 1}", "responsible_user_id": owners[n % 3]})["id"]
    A("POST", f"/gages/{gages['DEMO-PIN-005']}/transitions", {"target": "INACTIVE", "reason": "[DEMO] Dado de baja"})
    A("POST", f"/gages/{gages['DEMO-TOR-003']}/transitions", {"target": "OUT_OF_SERVICE",
                                                              "reason": "[DEMO] Golpe en el cabezal"})
    A("POST", f"/gages/{gages['DEMO-CAL-006']}/transfer", {"location": "[DEMO] Línea 2 · Ensamble",
                                                           "responsible_user_id": uid["tomás"],
                                                           "reason": "[DEMO] Reasignación de línea"})

    # Calibration history for the charts, and calibrations in each intermediate state.
    for code, days, found in (("DEMO-CAL-004", -5, "10.004"), ("DEMO-MIC-003", -12, "9.996"),
                              ("DEMO-IND-003", -3, "10.010"), ("DEMO-TOR-002", -8, "10.001"),
                              ("DEMO-CAL-007", -1, "9.990"), ("DEMO-MIC-005", -2, "10.000")):
        calibrate(code, days, found)
    for code, steps in (("DEMO-PIN-004", 1), ("DEMO-MIC-004", 2), ("DEMO-CAL-005", 3)):
        act = A("POST", "/calibrations", {"gage_id": gages[code], "activity_type": "INTERNAL_CALIBRATION",
                                          "planned_date": iso(2)})
        A("POST", f"/calibrations/{act['id']}/request", {})
        if steps >= 2:
            A("POST", f"/calibrations/{act['id']}/schedule", {"scheduled_date": iso(2), "technician_id": uid["tomás"]})
        if steps >= 3:
            T("POST", f"/calibrations/{act['id']}/start")

    std2 = A("POST", "/standards", {"standard_code": "DEMO-STD-TQ01", "description": "[DEMO] Analizador de torque",
                                    "category": "REFERENCE_INSTRUMENT", "plant_id": slp,
                                    "calibration_frequency_days": 365})
    c.post(f"/api/v1/standards/{std2['id']}/certificates", headers=A.h,
           data={"certificate_number": "DEMO-CERT-002", "issuer": "[DEMO] Laboratorio Acreditado",
                 "calibration_date": iso(-340), "issue_date": iso(-338), "traceability": "[DEMO] Patrón nacional"},
           files={"file": ("demo-cert-2.pdf", pdf_bytes("[DEMO] Certificado analizador"), "application/pdf")})

    # Competencies: catalog, profiles, training and evaluation records.
    comps = [A("POST", "/competency/competencies", {"code": code, "name": f"[DEMO] {name}", "validity_months": m})
             for code, name, m in (("CAL-DIM", "Calibración dimensional", 24), ("MSA-GRR", "Estudios GRR", 36),
                                   ("TORQUE", "Verificación de torquímetros", 12))]
    for who, title, prof in (("tomás", "Técnico de metrología", ["INTERNAL_CALIBRATOR", "VERIFIER"]),
                             ("laura", "Técnica de laboratorio", ["VERIFIER"]),
                             ("mario", "Gerente de metrología", ["INTERNAL_CALIBRATOR"])):
        M("PUT", f"/competency/people/{uid[who]}", {"job_title": f"[DEMO] {title}", "profile_types": prof})
    for who, comp, kind, days, result in (
            ("tomás", 0, "EVALUATION", -200, "PASSED"), ("tomás", 1, "TRAINING", -90, "PASSED"),
            ("laura", 0, "TRAINING", -30, "PASSED"), ("laura", 2, "EVALUATION", -400, "PASSED"),
            ("mario", 1, "EVALUATION", -60, "PASSED"), ("tomás", 2, "EVALUATION", -10, "FAILED")):
        M("POST", "/competency/records", {"user_id": uid[who], "competency_id": comps[comp]["id"], "record_type": kind,
                                          "title": comps[comp]["name"], "completed_on": iso(days), "result": result})

    # Laboratory: requests waiting for a decision, one scheduled, and a technician absence.
    S = Actor(login(people["sergio"][1]), org)
    for pn, prio, decide in (("DEMO-PN-5120", "NORMAL", False), ("DEMO-PN-6033", "URGENT", False),
                             ("DEMO-PN-7781", "HIGH", True)):
        r = S("POST", "/lab/requests", {"plant_id": mty, "service_id": svc["id"], "part_number": pn,
                                        "part_revision": "A", "description": f"[DEMO] Inspección {pn}",
                                        "priority": prio, "requested_date": iso(7), "customer_type": "INTERNAL",
                                        "customer_name": "[DEMO] Producción"})
        if decide:
            A("POST", f"/lab/requests/{r['id']}/decision", {"approve": True, "committed_date": iso(6)})
            wo = A("POST", "/lab/work-orders", {"service_request_id": r["id"]})
            A("POST", f"/lab/work-orders/{wo['id']}/schedule", {"technician_id": uid["laura"],
                                                                "scheduled_start": f"{iso(1)}T15:00:00Z",
                                                                "scheduled_end": f"{iso(1)}T18:00:00Z",
                                                                "gage_ids": [gages["DEMO-CAL-004"]]})
    M("POST", "/lab/absences", {"user_id": uid["laura"], "start_date": iso(9), "end_date": iso(10),
                                "reason": "[DEMO] Capacitación externa"})

    # MSA: the remaining methodologies (nested, attribute, stability, type 1).
    study("GRR anidado (destructivo)", "GRR_NESTED_ANOVA", "DEMO-TOR-002", {},
          [{"operator": o, "part": p, "trial": t, "value": v} for o, p, t, v in NESTED_HAND])
    att_obs, att_design = attribute_data()
    study("Atributos pasa/no pasa", "ATTRIBUTE_AGREEMENT", "DEMO-PIN-001",
          {"categories": att_design["categories"], "part_reference": att_design["reference"],
           "accept_category": "G", "reject_category": "NG"},
          [{"operator": o["operator"], "part": o["part"], "trial": o["trial"], "category": o["value"]} for o in att_obs])
    study("Estabilidad mensual", "STABILITY", "DEMO-CAL-001", {"subgroup_size": 1, "reference": 11.5},
          [{"subgroup": i + 1, "trial": 1, "value": v} for i, v in enumerate([10, 12, 11, 13, 12, 11, 12, 10, 11, 12])])
    study("Tipo 1 (Cg/Cgk)", "TYPE1", "DEMO-MIC-005", {"reference": 10.0, "tolerance": 0.1, "resolution": 0.001},
          [{"trial": i + 1, "value": v} for i, v in enumerate(TYPE1_VALUES)])

    # OOT: a second case taken through the whole workflow to CLOSED.
    calibrate("DEMO-IND-001", -1, "10.04", left="10.00")
    case = A("GET", f"/oot/cases?gage_id={gages['DEMO-IND-001']}")[0]

    def flow(actor, code):
        actor("POST", f"/workflows/oot_case/{case['id']}/transitions", {"transition": code, "comment": "[DEMO]"})
    flow(A, "INVESTIGATE")
    A("POST", f"/oot/cases/{case['id']}/analysis")
    A("POST", f"/oot/cases/{case['id']}/items", {"ref_code": "[DEMO] LOTE-3310", "description": "[DEMO] Lote en almacén"})
    for item in A("GET", f"/oot/cases/{case['id']}/items"):
        A("POST", f"/oot/items/{item['id']}/assess", {"assessment": "NO_IMPACT", "note": "[DEMO] Sin impacto"})
    flow(A, "EVALUATE_IMPACT")
    A("PATCH", f"/oot/cases/{case['id']}", {"risk_level": "LOW", "risk_assessment": "[DEMO] Desviación de 0.02 mm",
                                            "disposition": "[DEMO] Liberar lote", "customer_notification_required": False})
    action = A("POST", f"/oot/cases/{case['id']}/actions", {
        "action_type": "REINSPECTION", "description": "[DEMO] Remedir muestras retenidas", "owner_id": uid["tomás"],
        "due_date": iso(3)})
    flow(A, "PLAN_ACTIONS")
    flow(A, "SUBMIT")
    flow(M, "REVIEW")
    flow(P, "APPROVE")
    T("POST", f"/oot/actions/{action['id']}/finish", {"note": "[DEMO] Muestras dentro de tolerancia"})
    A("POST", f"/oot/cases/{case['id']}/release-gage", {"reason": "[DEMO] As Left dentro de tolerancia"})
    flow(A, "CLOSE")

    # Configuration: versioned custom fields, a form and a business rule (second-person approval when required).
    def propose(kind, definition, summary):
        v = A("POST", "/config/items", {"kind": kind, "definition": definition, "change_summary": summary})
        if v["status"] == "DRAFT":
            P("POST", f"/config/versions/{v['id']}/approve", {"comment": "[DEMO] Aprobado"})
    propose("CUSTOM_FIELD", {"entity_type": "gage", "key": "supplier_code", "label": "Código de proveedor",
                             "field_type": "TEXT", "text_format": "UPPERCASE_CODE", "max_length": 12},
            "[DEMO] Código de proveedor")
    propose("CUSTOM_FIELD", {"entity_type": "gage", "key": "ppap_level", "label": "Nivel PPAP", "field_type": "LIST",
                             "options": ["1", "2", "3", "4", "5"]}, "[DEMO] Nivel PPAP")
    propose("FORM", {"entity_type": "gage", "sections": [
        {"title": "Proveedor", "fields": ["supplier_code", "ppap_level", "manufacturer"]}]}, "[DEMO] Formulario")
    propose("BUSINESS_RULE", {"entity_type": "msa_study", "name": "[DEMO] GRR máximo para revisión",
                              "transitions": ["SUBMIT"], "conditions": [{"fact": "pct_sv_grr", "op": "lte", "value": 30}],
                              "message": "GRR mayor a 30 %"}, "[DEMO] Regla GRR")
    for code, sup, lvl in (("DEMO-MIC-001", "SUP-MITU", "3"), ("DEMO-CAL-001", "SUP-DEMO", "2")):
        A("PUT", f"/custom-fields/gage/{gages[code]}", {"values": {"supplier_code": sup, "ppap_level": lvl}})

    # Integrations: API key, webhook, simulated device readings, a committed import.
    A("POST", "/integrations/api-clients", {"name": "[DEMO] ERP lectura", "role_code": "viewer"})
    A("POST", "/integrations/webhooks", {"name": "[DEMO] ERP eventos", "url": f"https://erp.{DOMAIN}/hooks",
                                         "event_types": ["gage.created"]})
    dev = A("POST", "/integrations/devices", {"device_code": "DEMO-SIM-01", "name": "[DEMO] Simulador micrómetro",
                                              "adapter": "simulator", "plant_id": mty, "gage_id": gages["DEMO-MIC-002"]})
    A("POST", f"/integrations/devices/{dev['id']}/simulate", {"nominal": 10, "sigma": 0.002, "count": 25})
    csv = ("Gage ID,Descripcion,Tipo,Planta,Frecuencia\nDEMO-IMP-001,[DEMO] Vernier importado,CAL,MTY,365\n"
           "DEMO-IMP-002,[DEMO] Indicador importado,IND,SLP,180\n")
    r = c.post("/api/v1/integrations/imports", headers=A.h, data={"importer": "gages"},
               files={"file": ("demo-import.csv", csv.encode())})
    if r.status_code != 201 or r.json()["status"] != "VALIDATED":
        raise RuntimeError(f"import -> {r.status_code} {r.text[:400]}")
    A("POST", f"/integrations/imports/{r.json()['id']}/commit")


if __name__ == "__main__":
    main()
