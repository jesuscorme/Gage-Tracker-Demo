# Gage Tracker — Metrology Management System

Plataforma modular y multi-tenant para la gestión de instrumentos de medición (automotriz / IATF 16949).

- **Backend:** Python 3.12 · FastAPI · SQLAlchemy 2 · Alembic · PostgreSQL 16
- **Frontend:** Next.js 15 · React 19 · TypeScript · Tailwind CSS 4
- **Estado:** Fases 0–1 completas, Fase 2 (Gage Management) en avance. Ver [docs/MASTER_IMPLEMENTATION_PLAN.md](docs/MASTER_IMPLEMENTATION_PLAN.md).

## Estructura

```
backend/            API FastAPI (monolito modular)
  app/core/         configuración, BD, errores, logging, seguridad
  app/modules/      identity · organizations · audit · gages · dashboard · health
  alembic/          migraciones versionadas
  tests/            pruebas unitarias e integración (PostgreSQL real)
frontend/           Next.js (App Router)
  src/app/          pantallas
  src/components/   componentes reutilizables (UI, shell, formularios)
  src/lib/          cliente API, auth, i18n (es/en), tipos
docs/               plan maestro, línea base, ADRs, roadmap, reporte de avance
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

## Ejecución con Docker

```bash
docker compose up --build    # web :3000 · API :8000 · PostgreSQL :5433
```

> Los archivos Docker están escritos pero **no se han probado** en este entorno (Docker no instalado).

## Pruebas

```powershell
cd backend;  .venv\Scripts\python -m pytest        # requiere TEST_DATABASE_URL (ver .env.example)
cd frontend; npm test; npm run typecheck; npm run build
```

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
