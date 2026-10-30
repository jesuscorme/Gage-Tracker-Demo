"""Gage Management completion: dates, transfers, documents, import and export."""

import io
from datetime import timedelta

import pytest
from openpyxl import Workbook, load_workbook
from sqlalchemy import text

from tests.conftest import PDF, PNG, today


@pytest.fixture()
def org(make_org, gage_type, add_user):
    admin = make_org("Inventory")
    admin.type_id = gage_type(admin, "CAL", 365)["id"]
    admin.manager = add_user(admin, "metrology_manager")
    admin.tech = add_user(admin, "metrology_technician")
    return admin


def _ago(n):
    return (today() - timedelta(days=n)).isoformat()


def test_acquisition_and_in_service_dates(org, new_gage):
    g = new_gage(org, org.type_id, acquisition_date=_ago(400), in_service_date=_ago(390))
    assert g["acquisition_date"] == _ago(400) and g["in_service_date"] == _ago(390)
    r = org.post("/api/v1/gages", json={"gage_code": "D-2", "description": "Gage", "gage_type_id": org.type_id,
                                        "plant_id": org.plant_id, "acquisition_date": _ago(10),
                                        "in_service_date": _ago(20)})
    assert r.status_code == 422


def test_transfer_reassigns_and_records_history(org, new_gage):
    g = new_gage(org, org.type_id, location="Crib")
    dept = org.post("/api/v1/departments", json={"plant_id": org.plant_id, "code": "QA", "name": "Quality"}).json()
    body = {"department_id": dept["id"], "location": "Line 4", "responsible_user_id": org.tech.user_id,
            "reason": "Assigned to line 4 audit"}
    assert org.tech.post(f"/api/v1/gages/{g['id']}/transfer", json=body).status_code == 403
    r = org.manager.post(f"/api/v1/gages/{g['id']}/transfer", json=body)
    assert r.status_code == 200
    assert r.json()["location"] == "Line 4" and r.json()["responsible"]["id"] == org.tech.user_id
    moves = org.get(f"/api/v1/gages/{g['id']}/movements").json()
    assert moves[0]["changes"]["location"] == ["Crib", "Line 4"]
    assert moves[0]["changes"]["responsible"] == [None, "metrology_technician user"]
    assert moves[0]["reason"] == "Assigned to line 4 audit"
    assert org.manager.post(f"/api/v1/gages/{g['id']}/transfer",
                            json={"location": "Line 4", "reason": "again"}).json()["error"]["code"] == "no_changes"
    # Assignment can no longer be changed by an ordinary edit.
    assert org.patch(f"/api/v1/gages/{g['id']}", json={"location": "X"}).status_code == 422


def test_transfer_to_other_plant_clears_department(org, new_gage):
    dept = org.post("/api/v1/departments", json={"plant_id": org.plant_id, "code": "QA", "name": "Quality"}).json()
    g = new_gage(org, org.type_id, department_id=dept["id"])
    p2 = org.post("/api/v1/plants", json={"code": "P2", "name": "Plant 2"}).json()
    r = org.post(f"/api/v1/gages/{g['id']}/transfer", json={"plant_id": p2["id"], "reason": "Plant transfer"})
    assert r.json()["plant"]["code"] == "P2" and r.json()["department"] is None


def test_documents_upload_validation_download_and_withdrawal(org, new_gage, client):
    g = new_gage(org, org.type_id)
    files = {"file": ("manual.pdf", PDF, "application/pdf")}
    data = {"entity_type": "gage", "entity_id": g["id"], "category": "DOCUMENT", "title": "User manual"}
    r = org.tech.post("/api/v1/attachments", data=data, files=files)
    assert r.status_code == 201, r.text
    doc = r.json()
    assert doc["content_type"] == "application/pdf" and len(doc["sha256"]) == 64
    photo = org.post("/api/v1/attachments", data=data | {"category": "PHOTO"},
                     files={"file": ("p.png", PNG, "image/png")})
    assert photo.status_code == 201
    # Content must match the extension; executables and disguised files are rejected.
    bad = org.post("/api/v1/attachments", data=data, files={"file": ("x.pdf", b"MZ\x90\x00binary", "application/pdf")})
    assert bad.status_code == 422 and bad.json()["error"]["code"] == "invalid_file_type"
    exe = org.post("/api/v1/attachments", data=data, files={"file": ("x.exe", b"MZ", "application/octet-stream")})
    assert exe.status_code == 422
    not_photo = org.post("/api/v1/attachments", data=data | {"category": "PHOTO"}, files=files)
    assert not_photo.json()["error"]["code"] == "image_required"

    dl = org.get(f"/api/v1/attachments/{doc['id']}/download")
    assert dl.status_code == 200 and dl.content == PDF and dl.headers["content-type"] == "application/pdf"
    listed = org.get(f"/api/v1/attachments?entity_type=gage&entity_id={g['id']}").json()
    assert {a["category"] for a in listed} == {"DOCUMENT", "PHOTO"}

    viewer_like = org.post(f"/api/v1/attachments/{doc['id']}/remove", json={"reason": "Wrong file"})
    assert viewer_like.status_code == 200 and viewer_like.json()["removed_at"]
    assert len(org.get(f"/api/v1/attachments?entity_type=gage&entity_id={g['id']}").json()) == 1


def test_documents_are_isolated_between_tenants(org, new_gage, make_org):
    g = new_gage(org, org.type_id)
    doc = org.post("/api/v1/attachments", data={"entity_type": "gage", "entity_id": g["id"]},
                   files={"file": ("m.pdf", PDF, "application/pdf")}).json()
    other = make_org("Other")
    assert other.get(f"/api/v1/attachments/{doc['id']}/download").status_code == 404
    assert other.get(f"/api/v1/attachments?entity_type=gage&entity_id={g['id']}").status_code == 404
    r = other.post("/api/v1/attachments", data={"entity_type": "gage", "entity_id": g["id"]},
                   files={"file": ("m.pdf", PDF, "application/pdf")})
    assert r.status_code == 404


def _csv(rows: list[str]) -> bytes:
    header = "gage_code,description,gage_type_code,plant_code,department_code,location,responsible_email," \
             "serial_number,calibration_frequency_days,last_calibration_date,criticality"
    return ("\n".join([header, *rows]) + "\n").encode("utf-8")


def test_import_is_all_or_nothing_with_row_errors(org):
    bad = _csv([
        f"IMP-1,Caliper 150,CAL,P1,,Crib,,S1,,{_ago(10)},HIGH",
        "IMP-2,Micrometer,NOPE,P1,,,,S2,,,",
        "IMP-1,Duplicate,CAL,P1,,,,S3,,,",
        f"IMP-3,Future,CAL,P1,,,,S4,,{(today() + timedelta(days=3)).isoformat()},",
    ])
    r = org.post("/api/v1/gages/import", files={"file": ("inv.csv", bad, "text/csv")})
    assert r.status_code == 200, r.text
    res = r.json()
    assert res["created"] == 0 and res["total_rows"] == 4
    assert [e["row"] for e in res["errors"]] == [3, 4, 5]
    assert "NOPE" in res["errors"][0]["errors"][0]
    assert org.get("/api/v1/gages?q=IMP").json()["total"] == 0  # nothing partially saved


def test_import_dry_run_then_commit_csv_and_xlsx(org):
    good = _csv([f"IMP-1,Caliper 150,CAL,P1,,Crib,{org.email},S1,180,{_ago(10)},HIGH",
                 "IMP-2,Micrometer 25,CAL,P1,,,,S2,,,"])
    dry = org.post("/api/v1/gages/import?dry_run=true", files={"file": ("inv.csv", good, "text/csv")}).json()
    assert dry["dry_run"] and dry["valid_rows"] == 2 and dry["created"] == 0 and not dry["errors"]
    assert org.get("/api/v1/gages?q=IMP").json()["total"] == 0
    res = org.post("/api/v1/gages/import", files={"file": ("inv.csv", good, "text/csv")}).json()
    assert res["created"] == 2
    g1 = org.get("/api/v1/gages?q=IMP-1").json()["items"][0]
    assert g1["calibration_frequency_days"] == 180 and g1["responsible"]["full_name"] == "Inventory Admin"

    wb = Workbook()
    ws = wb.active
    ws.append(["gage_code", "description", "gage_type_code", "plant_code"])
    ws.append(["XL-1", "Height gage", "CAL", "P1"])
    buf = io.BytesIO()
    wb.save(buf)
    r = org.post("/api/v1/gages/import", files={"file": ("inv.xlsx", buf.getvalue(), "application/octet-stream")})
    assert r.json()["created"] == 1


def test_import_requires_permission(org):
    r = org.tech.post("/api/v1/gages/import", files={"file": ("inv.csv", _csv([]), "text/csv")})
    assert r.status_code == 403
    assert org.get("/api/v1/gages/import/template").text.lstrip("﻿").startswith("gage_code,")


def test_export_inventory_respects_filters(org, new_gage):
    new_gage(org, org.type_id, "EX-1", last_calibration_date=_ago(5))
    new_gage(org, org.type_id, "EX-2")
    csv_ = org.get("/api/v1/gages/export?format=csv&status=OVERDUE")
    assert csv_.status_code == 200 and "attachment" in csv_.headers["content-disposition"]
    lines = csv_.content.decode("utf-8-sig").strip().splitlines()
    assert len(lines) == 2 and lines[1].startswith("EX-2,")
    xl = org.get("/api/v1/gages/export?format=xlsx")
    ws = load_workbook(io.BytesIO(xl.content)).active
    assert [c.value for c in ws[1]][:2] == ["Gage ID", "Description"] and ws.max_row == 3


def test_movement_history_is_append_only(org, new_gage, db):
    g = new_gage(org, org.type_id)
    org.post(f"/api/v1/gages/{g['id']}/transfer", json={"location": "A", "reason": "move"})
    with pytest.raises(Exception, match="append-only"):
        with db.begin_nested():
            db.execute(text("DELETE FROM gage_movements WHERE gage_id = :g"), {"g": g["id"]})
