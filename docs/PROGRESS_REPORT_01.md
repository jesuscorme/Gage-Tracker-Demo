# Reporte de avance 01 — primer incremento (~20 %)

**Fecha:** 2026-10-29 · **Avance global estimado:** ≈ 18 % (ver `IMPLEMENTATION_ROADMAP.md`)

## 1. Fases

| Fase | Estado |
|---|---|
| 0 · Descubrimiento | **Completa** — `PROJECT_BASELINE.md`, `ARCHITECTURE_DECISIONS.md`, `IMPLEMENTATION_ROADMAP.md` |
| 1 · Fundaciones | **Completa** salvo pendientes no bloqueantes (OIDC, rate limiting, Docker sin probar) |
| 2 · Gage Management | **Parcial (~65 %)** — CRUD, estados, filtros, historial y auditoría listos; faltan documentos, exportación y unicidad configurable |

## 2. Funcionalidades implementadas y probadas

**Plataforma**
- Registro de organización (crea organización + primera planta + administrador), login, perfil e idioma preferido.
- Multi-tenancy con contexto por request y aislamiento entre organizaciones; alcance por planta dentro de la organización.
- RBAC con 13 permisos y 5 roles de sistema; validación siempre en backend.
- Gestión de usuarios (alta, rol, plantas, activación) con protección del último administrador.
- Organización (ventana Due Soon, zona horaria), plantas y departamentos.
- Audit trail append-only (trigger en BD) con diffs, actor, motivo, IP y request id.
- Errores centralizados con formato único, logging JSON con `X-Request-ID`, health checks `live`/`ready`.
- Configuración por ambiente; la app no arranca en producción con secretos débiles.

**Gage Management**
- Catálogo de tipos (con frecuencia por defecto, activación/desactivación).
- Registro completo: Gage ID, descripción, tipo, fabricante, modelo, serie, rango, unidad, resolución, exactitud, criticidad, organización, planta, departamento, ubicación, responsable, frecuencia, última calibración, próximo vencimiento, estado.
- Listado con búsqueda, filtros (estado, planta, tipo, disponibilidad, inactivos), ordenamiento y paginación.
- Expediente individual con estado, disponibilidad, historial de estados y registro de cambios.
- Edición con campos sensibles protegidos; baja lógica y reactivación.
- Estados Calibrated / Due Soon / Overdue / Out of Service / In Calibration / Inactive según ADR-006; liberación solo con `gages:release`.
- Dashboard con KPIs calculados en vivo (sin cifras ficticias).

## 3. Arquitectura

Monolito modular FastAPI (`identity`, `organizations`, `audit`, `gages`, `dashboard`, `health`) + Next.js con proxy same-origin. Detalle en `ARCHITECTURE_DECISIONS.md`.

## 4. Base de datos

**Tablas (13):** `organizations`, `plants`, `departments`, `users`, `roles`, `permissions`, `role_permissions`, `organization_memberships`, `plant_memberships`, `audit_events`, `gage_types`, `gages`, `gage_status_history` (+ `alembic_version`).

**Migraciones:**
| Revisión | Contenido |
|---|---|
| `0001_platform_foundation` | Tenants, plantas, departamentos, usuarios, RBAC (semilla de permisos y roles), audit trail + trigger append-only |
| `0002_gage_management` | Tipos, instrumentos (CHECKs de estado, frecuencia, rango, resolución; índices), historial de estado append-only, permisos de instrumentos |

Ejecutadas desde base limpia (upgrade → downgrade base → upgrade) en cada corrida de pruebas y en la BD de desarrollo. `alembic check`: sin diferencias entre modelos y migraciones.

## 5. Endpoints (`/api/v1`, salvo health)

| Método | Ruta | Permiso |
|---|---|---|
| GET | `/health/live`, `/health/ready` | — |
| POST | `/auth/register`, `/auth/login` | — |
| GET/PATCH | `/auth/me` | autenticado |
| GET | `/roles`, `/users` | `users:read` |
| POST/PATCH | `/users`, `/users/{id}` | `users:manage` |
| GET / PATCH | `/organization` | `organization:read` / `organization:manage` |
| GET / POST, PATCH | `/plants`, `/departments` | `organization:read` / `plants:manage` |
| GET | `/audit-events` | `audit:read` |
| GET / POST, PATCH | `/gage-types` | `gages:read` / `gage_types:manage` |
| GET | `/gages`, `/gages/{id}`, `/gages/{id}/status-history`, `/gages/{id}/audit` | `gages:read` |
| POST | `/gages` | `gages:create` |
| PATCH | `/gages/{id}` | `gages:update` (+ `gages:release` para fecha/frecuencia) |
| POST | `/gages/{id}/transitions` | según transición: `restrict` / `release` / `retire` |
| GET | `/dashboard/summary` | `gages:read` |

OpenAPI interactivo: `/api/docs` (deshabilitado en producción).

## 6. Pantallas

Login · Registro de organización · Layout (menú lateral con módulos futuros bloqueados, header con organización, alcance de plantas, selector ES/EN, usuario) · Dashboard · Instrumentos (listado/filtros) · Nuevo instrumento · Expediente · Edición · Tipos de instrumento · Organización y plantas · Usuarios y roles · Audit trail. Responsive (verificado a 390 px sin scroll horizontal).

## 7. Pruebas ejecutadas (resultados reales)

| Suite | Resultado |
|---|---|
| Backend pytest (PostgreSQL 16 real) | **73 / 73 PASS** — plataforma 13, RBAC 11, aislamiento 9, reglas de estado 20, instrumentos 20 |
| Frontend Vitest | **6 / 6 PASS** (paridad de traducciones, metadatos de estado/transiciones) |
| TypeScript `tsc --noEmit` | PASS |
| `next build` producción | PASS |
| E2E navegador (Playwright + Edge, app real: Next.js → FastAPI → PostgreSQL) | **13 / 13 PASS**, sin errores de página |

Escenarios E2E: registro, tipo, departamento, alta completa, instrumento sin calibración = Overdue, restricción + liberación autorizada, filtros y búsqueda, edición, dashboard, alta de técnico, límites del técnico (UI y **403 del backend ante llamada directa**), aislamiento entre organizaciones en navegador (404), interfaz en inglés y vista móvil. Los datos E2E se marcaron `[E2E]` y la BD de desarrollo se restableció al terminar.

**No ejecutado:** `docker compose up` (Docker no instalado). El script E2E vive fuera del repositorio (validación de esta sesión); incorporarlo como suite permanente es un pendiente.

## 8. Problemas encontrados y corregidos

1. `email-validator` rechaza dominios reservados (`.test`) → datos de prueba con `example.com`.
2. Decimales serializados distinto según origen (`0.01` vs `0.010000`) → normalización en salida.
3. `dict(Result)` tratado como mapping → comprensión explícita.
4. `now()` devuelve la hora de inicio de transacción y desordenaba el historial → `clock_timestamp()` en eventos.
5. Pruebas lentas por bcrypt → `BCRYPT_ROUNDS` configurable (4 solo en pruebas; ≥ 12 obligatorio en producción).
6. Puertos 3000/3100/8000 ocupados por otros proyectos del equipo → validación en 3200/8100; documentado.
7. Encabezados de tabla ordenables sin estilo uniforme; menú lateral no llegaba al final en páginas largas → corregido.

## 9. Pendientes

- Fase 2: documentos/adjuntos, exportación, unicidad configurable, asignaciones, concurrencia optimista.
- Fase 1: OIDC, rate limiting de login, cookie httpOnly, RLS, validar Docker.
- Suite E2E dentro del repositorio y CI.

## 10. Riesgos técnicos

Ver `PROJECT_BASELINE.md` §4. Principales: autenticación local sin OIDC/rate limiting, token en `sessionStorage`, aislamiento sin RLS, fecha de calibración manual provisional hasta Fase 3.
