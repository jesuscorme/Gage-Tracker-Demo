# Gage Tracker — Metrology Management System

Plataforma modular y multi-tenant para la gestión de instrumentos de medición (automotriz / IATF 16949).

- **Backend:** Python 3.12 · FastAPI · SQLAlchemy 2 · Alembic · PostgreSQL 16
- **Frontend:** Next.js 15 · React 19 · TypeScript · Tailwind CSS 4
- **Versión `1.0.0-rc.1` (Release Candidate, ≈ 84 % del alcance; no liberada a producción).** Todos los módulos conectados: plataforma, instrumentos, calibración, patrones, competencias, laboratorio, MSA (motor validado), OOT, integraciones, configuración, cumplimiento, tablero ejecutivo y reportes. Estado y pendientes: [docs/MASTER_IMPLEMENTATION_PLAN.md](docs/MASTER_IMPLEMENTATION_PLAN.md) · cierre: [docs/PROGRESS_REPORT_04.md](docs/PROGRESS_REPORT_04.md).

## Estructura

```
backend/            API FastAPI (monolito modular)
  app/core/         configuración, BD, errores, logging, seguridad
  app/engine/       motor estadístico MSA (independiente de API y BD)
  app/modules/      identity · organizations · audit · documents · gages · standards · competency
                    calibration · laboratory · notifications · dashboard · health
                    msa · oot · configuration · events · integrations · compliance · reports
  alembic/          migraciones versionadas
  tests/            pruebas unitarias e integración (PostgreSQL real)
frontend/           Next.js (App Router)
  src/app/          pantallas
  src/components/   componentes reutilizables (UI, shell, formularios)
  src/lib/          cliente API, auth, i18n (es/en), tipos
docs/               plan maestro, línea base, ADRs, roadmap, reporte de avance
edge/edge_agent.py  agente de referencia del Edge Connector (cola local store-and-forward)
deploy/             paquete de instalación privada / producción (compose, Caddy, .env.example, backup/restore)
scripts/            backup.ps1 · restore.ps1 · demo-reset.ps1 · dev-db.ps1
scripts/dev-db.ps1  PostgreSQL local sin Docker
docker-compose.yml  stack de desarrollo con Docker
```

## Ejecución local (sin Docker, Windows)

Requisitos: Python 3.12, Node 22+ (probado con 24), PostgreSQL 16 instalado (solo sus binarios).

```powershell
# 1. Base de datos local en localhost:5433 (cluster privado en .local/, no toca otras instancias)
powershell -File scripts/dev-db.ps1 start

# 2. Backend
cd backend
python -m venv .venv
.venv\Scripts\python -m pip install -r requirements-dev.txt
copy .env.example .env
.venv\Scripts\python -m alembic upgrade head
.venv\Scripts\python -m uvicorn app.main:app --port 8000      # http://localhost:8000/api/docs

# 3. Frontend (otra terminal)
cd frontend
npm ci
copy .env.example .env.local        # API_URL=http://localhost:8000
npm run dev                          # http://localhost:3000
```

Si los puertos 8000/3000 están ocupados, use otros: `uvicorn ... --port 8100` y
`API_URL=http://localhost:8100` + `npx next dev -p 3200`. En `next build`/`next start`
el valor de `API_URL` se fija en tiempo de build.

Abra http://localhost:3000/register para crear la primera organización (planta + administrador).
No se cargan datos de ejemplo.

**Arranque de una organización nueva:** crear tipos de instrumento → registrar usuarios con su rol →
**otorgar autorizaciones** en *Competencias → Autorizaciones* (calibración interna, revisión técnica,
aprobación, servicio de laboratorio, inspección dimensional) → registrar patrones con su certificado →
dar de alta servicios del laboratorio en *Configuración técnica*. Sin autorizaciones vigentes el sistema
no permite ejecutar, revisar ni aprobar actividades restringidas (comportamiento intencional). Para calcular estudios MSA
se requiere la autorización `MSA_EVALUATION`. Los criterios de aceptación MSA se crean (hay plantillas) y los aprueba
otro usuario en *MSA → Criterios MSA*; sin criterios aprobados los resultados no emiten decisión.

## Documentación

| Tema | Documento |
|---|---|
| Arquitectura · datos · API | [ARCHITECTURE](docs/ARCHITECTURE.md) · [DATABASE](docs/DATABASE.md) · [API](docs/API.md) |
| Seguridad | [SECURITY](docs/SECURITY.md) |
| Despliegue | [Privado](docs/DEPLOYMENT_PRIVATE.md) · [Nube](docs/DEPLOYMENT_CLOUD.md) · [Respaldo](docs/BACKUP_RESTORE.md) |
| Manuales | [Usuario](docs/USER_MANUAL.md) · [Administración](docs/ADMIN_MANUAL.md) |
| Calidad y liberación | [Pruebas](docs/TESTING.md) · [Notas de versión](docs/RELEASE_NOTES.md) · [UAT](docs/UAT.md) · [Defectos](docs/DEFECTS.md) |
| MSA · integraciones | [docs/msa](docs/msa/README.md) · [docs/integrations](docs/integrations/README.md) |

## Demo

`powershell -File scripts/demo-reset.ps1` reconstruye la base separada `gagetracker_demo` con datos **ficticios** marcados [DEMO] (usuarios `@demo.example.com`, contraseña en `DEMO_PASSWORD`, por defecto `Demo-GageTracker-2026`). Nunca toca otras bases.

## Ejecución con Docker

```bash
docker compose up --build    # web :3000 · API :8000 · PostgreSQL :5433
```

> Desarrollo: `docker-compose.yml`. Producción / instalación privada: `deploy/docker-compose.yml` (ver docs/DEPLOYMENT_PRIVATE.md). **Ninguno se ha ejecutado** en este entorno (Docker no instalado).

## Pruebas

```powershell
cd backend;  .venv\Scripts\python -m pytest        # requiere TEST_DATABASE_URL (ver .env.example)
cd frontend; npm test; npm run typecheck; npm run build
```

Lint: `ruff check app tests scripts alembic`. Rendimiento: `python -m scripts.perf_check` (base dedicada). CI propuesto: `.github/workflows/ci.yml`.

La suite de backend reconstruye el esquema en la BD de pruebas mediante las migraciones
(upgrade → downgrade base → upgrade) en cada ejecución.

## Variables de entorno (backend)

| Variable | Descripción |
|---|---|
| `APP_ENV` | `development` · `test` · `production` |
| `DATABASE_URL` | URL SQLAlchemy de PostgreSQL |
| `JWT_SECRET` | Obligatorio y ≥ 32 caracteres en producción (la app no arranca si no) |
| `ACCESS_TOKEN_TTL_MINUTES` | Vigencia del token (default 60) |
| `BCRYPT_ROUNDS` | Factor de costo bcrypt (≥ 12 en producción) |
| `CORS_ORIGINS` | Orígenes permitidos (el frontend usa proxy same-origin) |
| `ALLOW_SELF_REGISTRATION` | Permite crear organizaciones desde `/register` |
| `LOG_LEVEL`, `LOG_JSON` | Logging estructurado |
| `STORAGE_DIR` | Carpeta de documentos subidos (certificados, fotos, informes). Respaldar junto con la BD |
| `MAX_UPLOAD_MB` | Tamaño máximo por archivo (default 20) |
| `SCHEDULER_ENABLED`, `SCHEDULER_INTERVAL_SECONDS` | Tareas de fondo: webhooks, escalamientos, barrido de vencidos |
| `WEBHOOK_ALLOW_HTTP`, `WEBHOOK_TIMEOUT_SECONDS` | Webhooks (en producción solo https) |
| `SECRET_ENCRYPTION_KEY` | Clave Fernet para secretos en reposo (obligatoria en producción) |
| `LOGIN_MAX_FAILURES`, `LOGIN_LOCKOUT_MINUTES` | Bloqueo por intentos fallidos (5 / 15 min) |
| `PASSWORD_RESET_TTL_MINUTES` | Vigencia del enlace de restablecimiento (60) |
