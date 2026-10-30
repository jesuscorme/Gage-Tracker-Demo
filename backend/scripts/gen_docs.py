"""Generate the reference parts of docs/DATABASE.md and docs/API.md from the code.

    python -m scripts.gen_docs            (needs DATABASE_URL to read the real triggers)
"""

import pathlib
from collections import defaultdict

from sqlalchemy import create_engine, text

import app.models  # noqa: F401
from app.core.config import get_settings
from app.core.db import Base
from app.main import create_app

DOCS = pathlib.Path(__file__).resolve().parents[2] / "docs"

PREFIX_MODULE = [
    ("organizations", "Plataforma"), ("plants", "Plataforma"), ("departments", "Plataforma"), ("users", "Plataforma"),
    ("roles", "Plataforma"), ("organization_memberships", "Plataforma"), ("plant_memberships", "Plataforma"),
    ("permissions", "Plataforma"), ("role_permissions", "Plataforma"), ("password_reset", "Plataforma"),
    ("audit", "Auditoría"), ("attachments", "Documentos"), ("code_sequences", "Plataforma"),
    ("gage", "Gage Management"), ("calibration", "Calibration"), ("standard", "Standards"),
    ("competenc", "Competency"), ("personnel", "Competency"), ("authorizations", "Competency"),
    ("notification", "Notificaciones"), ("lab_", "Laboratory"), ("service_requests", "Laboratory"),
    ("work_order", "Laboratory"), ("technician", "Laboratory"), ("inspection", "Laboratory"),
    ("measurement_reports", "Laboratory"), ("msa_", "MSA"), ("oot_", "OOT"), ("config", "Configuración"),
    ("custom_field", "Configuración"), ("workflow", "Configuración"), ("outbox", "Eventos"), ("api_", "Integraciones"),
    ("idempotency", "Integraciones"), ("webhook", "Integraciones"), ("import_jobs", "Integraciones"),
    ("device", "Integraciones"),
]


def module_of(table: str) -> str:
    for prefix, mod in PREFIX_MODULE:
        if table.startswith(prefix):
            return mod
    return "Otros"


def database() -> str:
    triggers = defaultdict(list)
    eng = create_engine(get_settings().database_url)
    with eng.connect() as c:
        for table, _name, fn in c.execute(text(
                "SELECT event_object_table, trigger_name, action_statement FROM information_schema.triggers "
                "WHERE trigger_schema = 'public' GROUP BY 1, 2, 3 ORDER BY 1")):
            triggers[table].append(fn.replace("EXECUTE FUNCTION ", "").replace("()", ""))
        rev = c.execute(text("SELECT version_num FROM alembic_version")).scalar()
    by_mod = defaultdict(list)
    for t in Base.metadata.sorted_tables:
        by_mod[module_of(t.name)].append(t)
    out = [f"## Referencia de tablas (generada desde el código · revisión `{rev}` · {len(Base.metadata.tables)} tablas)\n",
           "Protección: `forbid_append_only_change` = solo inserción; `protect_measurement_row` = correcciones solo por "
           "reemplazo; `protect_config_version` / `protect_criteria_set` = contenido inmutable tras aprobación.\n"]
    for mod in sorted(by_mod):
        out.append(f"\n### {mod}\n\n| Tabla | Columnas | Relaciones (FK) | Protección en BD |\n|---|---|---|---|")
        for t in by_mod[mod]:
            fks = sorted({f"{fk.parent.name} → {fk.column.table.name}" for fk in t.foreign_keys
                          if fk.column.table.name not in ("organizations", "users")})
            prot = ", ".join(sorted(set(triggers.get(t.name, [])))) or "—"
            out.append(f"| `{t.name}` | {len(t.columns)} | {'; '.join(fks) or '—'} | {prot} |")
    return "\n".join(out) + "\n"


def api() -> str:
    spec = create_app().openapi()
    groups = defaultdict(list)
    for path, ops in spec["paths"].items():
        for method, op in ops.items():
            tag = (op.get("tags") or ["health"])[0]
            doc = (op.get("description") or "").strip().splitlines()[0] if op.get("description") else ""
            groups[tag].append((path, method.upper(), doc))
    total = sum(len(v) for v in groups.values())
    out = [f"## Inventario de endpoints (generado desde OpenAPI · {total} operaciones · versión "
           f"{spec['info']['version']})\n"]
    for tag in sorted(groups):
        out.append(f"\n### {tag}\n\n| Método | Ruta | Descripción |\n|---|---|---|")
        for path, m, doc in sorted(groups[tag]):
            out.append(f"| {m} | `{path}` | {doc} |")
    return "\n".join(out) + "\n"


def splice(name: str, generated: str) -> None:
    f = DOCS / name
    head = f.read_text(encoding="utf-8").split("<!-- GENERATED -->")[0]
    f.write_text(head + "<!-- GENERATED -->\n\n" + generated, encoding="utf-8")


if __name__ == "__main__":
    splice("DATABASE.md", database())
    splice("API.md", api())
    print("docs regenerated")
