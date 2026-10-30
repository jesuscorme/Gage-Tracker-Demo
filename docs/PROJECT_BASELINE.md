# Línea base del proyecto (Fase 0)

**Fecha:** 2026-10-29

## 1. Estado encontrado

| Elemento | Hallazgo |
|---|---|
| Repositorio remoto | `github.com/jesuscorme/Gage-Tracker-Demo` — **vacío** (sin commits) |
| Contenido local | Solo el plan maestro (`Gage_Tracker_Plan_Maestro_Claude_Code.md`), movido a `docs/MASTER_IMPLEMENTATION_PLAN.md` |
| Código existente | Ninguno — no hay stack, módulos, migraciones, autenticación ni pruebas que conservar |
| Entorno de la máquina | Python 3.12.10, Node 24.20, npm 11.19, PostgreSQL 16 (servicio Windows), Microsoft Edge. **Sin Docker**. |
| Puertos ocupados por otros procesos | 3000, 3100 (node) y 8000, 8010 (python) — pertenecen a otros proyectos del equipo; no se tocaron |

Al no existir código, no hubo funcionalidad que reutilizar ni riesgo de reescritura destructiva.
El plan indica esperar aprobación de la estructura en repositorios vacíos; el propietario solicitó
explícitamente la implementación del primer 20 %, por lo que se adoptó el stack propuesto en el
plan (§2.2) y las decisiones se registran en `ARCHITECTURE_DECISIONS.md`.

## 2. Stack adoptado

| Capa | Tecnología | Versión |
|---|---|---|
| API | FastAPI + Uvicorn | 0.115.14 / 0.32.1 |
| ORM / migraciones | SQLAlchemy 2 + Alembic | 2.0.55 / 1.14.1 |
| Driver | psycopg 3 | 3.2.13 |
| Base de datos | PostgreSQL | 16 |
| Auth | PyJWT (HS256) + bcrypt | 2.15.1 / 4.3.0 |
| Pruebas backend | pytest + httpx TestClient | 8.4.2 |
| Frontend | Next.js (App Router) + React | 15.5.4 / 19.1.1 |
| Estilos | Tailwind CSS | 4.1.13 |
| Pruebas frontend | Vitest | 3.2.4 |
| E2E (fuera del repo, validación) | Playwright + Edge | 1.55.0 |

## 3. Inventario de módulos (tras este avance)

| Módulo (plan §4.1) | Estado |
|---|---|
| Identity & Tenant Context | Implementado (`app/modules/identity`) |
| Administration (org, plantas, deptos., usuarios, roles) | Implementado parcialmente (sin roles personalizados) |
| Audit trail | Implementado (`app/modules/audit`) |
| Dashboard | Inicial: KPIs de instrumentos (`app/modules/dashboard`) |
| Gage Management | Primera versión funcional (`app/modules/gages`) |
| Calibration, MSA, Laboratory, Standards, OOT, Competency, Integrations, Compliance | No iniciados (visibles en menú como "Próximamente") |

## 4. Riesgos y pendientes priorizados

| # | Riesgo / pendiente | Impacto | Acción propuesta |
|---|---|---|---|
| 1 | Autenticación local (JWT) en lugar de OIDC/OAuth2 | Alto para clientes enterprise | ADR-004: incorporar OIDC en fase de Integrations o antes de piloto |
| 2 | Token en `sessionStorage` (riesgo XSS) | Medio | Migrar a cookie httpOnly / BFF junto con OIDC |
| 3 | Sin rate limiting en `/auth/login` | Medio | Añadir limitador (proxy o middleware) antes de exponer a internet |
| 4 | Aislamiento solo a nivel aplicación (sin RLS) | Medio | ADR-003: evaluar PostgreSQL RLS como defensa en profundidad |
| 5 | Docker no probado | Medio | Validar `docker compose up` en un equipo con Docker |
| 6 | Unicidad del Gage ID fija por organización (no configurable) | Bajo | Configurable en Fase 9 |
| 7 | Fecha de calibración registrada manualmente (provisional) | Medio | Sustituir por el flujo de Fase 3 |
| 8 | Sin documentos/adjuntos ni exportación en Gage Management | Medio | Completar Fase 2 |
| 9 | Sin control de concurrencia optimista en ediciones | Bajo | Añadir `version`/ETag |
