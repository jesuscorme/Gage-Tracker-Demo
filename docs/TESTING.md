# Pruebas y control de calidad

Estado al 2026-10-30, versión `1.0.0-rc.1`. Todas las cifras de este documento salen de ejecuciones reales.

## 1. Cómo ejecutar

```powershell
cd backend;  .venv\Scripts\python -m pytest -q          # requiere TEST_DATABASE_URL (PostgreSQL real)
             .venv\Scripts\python -m ruff check app tests scripts alembic
             $env:DATABASE_URL=$env:TEST_DATABASE_URL; .venv\Scripts\python -m alembic check
cd frontend; npx tsc --noEmit; npx vitest run; npm run build
```

Las pruebas E2E en navegador (Playwright con Edge) se ejecutaron contra una base dedicada (`gagetracker_e2e`), nunca contra datos reales. El pipeline de CI propuesto está en `.github/workflows/ci.yml` y **aún no se ha ejecutado** en un servidor de CI.

## 2. Resultados

| Tipo | Alcance | Resultado |
|---|---|---|
| Backend: unitarias, integración y API (PostgreSQL real) | 234 pruebas en 22 archivos | **234/234** |
| Validación estadística del motor | 48 casos: datasets publicados, implementaciones independientes, límites, diseños inválidos | **48/48** (incluidas en las 234) |
| Regresión estadística (*golden*) y PDF por método | Salida completa de los 8 métodos congelada; PDF de los 8 métodos en ES y EN | **8/8 + 16/16** (incluidas) |
| Migraciones | Subida completa, bajada completa y nueva subida en cada corrida; `alembic check` | OK, sin diferencias |
| Lint backend | ruff: errores de sintaxis y pyflakes | Sin hallazgos |
| Frontend | `tsc`, Vitest y `next build` | Tipos OK, **13/13**, compilación OK |
| E2E en navegador | Bloque 1: plataforma e instrumentos | **13/13** |
| | Bloque 2: calibración, laboratorio, patrones, importación | **9/9** |
| | Bloque 3: MSA, criterios, OOT, integraciones, configuración, cumplimiento | **13/13** |
| | Bloque 4: tablero, reportes, cuenta, restablecimiento, bloqueo, móvil, inglés | **8/8** |
| Auditoría de dependencias | pip-audit y npm audit | **0 vulnerabilidades conocidas** tras las actualizaciones |
| Concurrencia | 20 hilos sobre la numeración; 8 reintentos simultáneos con la misma clave de idempotencia | Sin duplicados (2/2) |
| Rendimiento | 5 000 instrumentos, 5 000 calibraciones, 20 000 eventos de auditoría | Ver §4 |
| Respaldo y restauración | Respaldo, restauración en base nueva, conteos, hashes, migración y *rollback* | Ver `BACKUP_RESTORE.md` |

Pruebas por archivo:

| Archivo | Pruebas |
|---|---|
| calibration | 16 |
| compliance | 2 |
| concurrency | 2 |
| configuration | 6 |
| dashboard | 2 |
| edge_agent | 1 |
| engine_grr | 34 |
| engine_other | 14 |
| engine_regression | 24 |
| gage_completion | 10 |
| gage_status | 20 |
| gages | 20 |
| integrations | 8 |
| laboratory | 7 |
| msa | 8 |
| oot | 5 |
| platform | 13 |
| rbac | 18 |
| reports | 4 |
| security | 5 |
| standards_competency | 5 |
| tenant_isolation | 10 |

## 3. Flujos funcionales cubiertos (E2E y pruebas de API)

| Flujo | Evidencia |
|---|---|
| Instrumentos: alta → asignación → consulta → calibración → actualización → historial | `test_gages*`, `test_calibration`, E2E 1–2 |
| Calibraciones: solicitud → ejecución → As Found → As Left → revisión → aprobación → liberación | `test_calibration`, `test_oot::calibrate`, E2E 2 |
| Patrones: alta → certificado → vigencia → uso → historial | `test_standards_competency`, reporte `standards_history` |
| Competencias: registro → formación → autorización → asignación de actividad | `test_standards_competency`, `test_*not_authorized*` |
| Laboratorio: solicitud → programación → orden → ejecución → medición → informe → cierre | `test_laboratory`, E2E 2, demo |
| MSA: configuración → captura → validación → cálculo → evaluación → reporte | `test_msa`, E2E 3 |
| OOT: detección → restricción → investigación → impacto → acciones → aprobación → cierre | `test_oot`, E2E 3 |
| Seguridad: sesiones, contraseñas, bloqueo, restablecimiento, cabeceras, archivos | `test_security`, E2E 4 |
| Multi-tenancy: URLs, ids, API, exportaciones, adjuntos, reportes, tablero | `test_tenant_isolation`, pruebas de aislamiento en cada módulo, `test_reports`, `test_dashboard` |
| Reportes conciliados con el tablero y los datos de origen | `test_reports::test_reports_reconcile_*`, `test_dashboard` |

## 4. Rendimiento (evidencia)

Script: `backend/scripts/perf_check.py`, en la base dedicada `gagetracker_perf`. Mediana de 5 llamadas en el equipo de desarrollo (Windows, PostgreSQL 16 local).

| Endpoint | Mediana (ms) | Máximo (ms) | Consultas SQL |
|---|---|---|---|
| `/dashboard/overview` | 114 | 201 | 26 |
| `/dashboard/summary` | 39 | 61 | 6 |
| `/gages?page_size=50` | 52 | 61 | 6 |
| `/gages?q=…` | 47 | 58 | 6 |
| `/calibrations?page_size=50` | 85 | 92 | 7 |
| `/reports/gage_inventory` (5 000 filas) | 374 | 412 | 5 |
| `/reports/calibrations_performed` (5 000 filas) | 366 | 398 | 5 |
| `/compliance/matrix` | 82 | 460 | 42 |
| `/exchange/gages?page_size=500` | 93 | 112 | 6 |
| `/audit-events?limit=50` | 18 | 21 | 6 |

Hallazgos:
- **No hay N+1.** El número de consultas por petición es constante y no crece con los datos.
- **Estadísticas desactualizadas:** antes de `ANALYZE`, `/dashboard/overview` tardó 4 827 ms con los mismos datos. La causa fueron las estadísticas tras una carga masiva, no el código. Mitigación: `ANALYZE` en los scripts de restauración; *autovacuum* lo hace en operación normal.
- **Cálculo MSA síncrono:** con estudios típicos (≤ 500 lecturas) tarda milisegundos. No se midieron estudios masivos.

## 5. Pendiente de pruebas

| Pendiente | Motivo |
|---|---|
| Despliegue con Docker (compose de producción e instalación privada) | Docker no está instalado en el equipo de desarrollo |
| Ejecución del pipeline de CI | No hay servidor de CI configurado |
| Pruebas de carga con usuarios concurrentes sostenidos | Fuera del alcance disponible |
| Prueba de penetración externa | Requiere un tercero |
| UAT con usuarios reales | Matriz en `UAT.md`; pendiente de ejecución por los responsables |
