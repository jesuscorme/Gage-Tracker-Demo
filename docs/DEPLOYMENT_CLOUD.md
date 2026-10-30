# Despliegue SaaS (nube)

> **Estado: documentado; configuración NO VALIDADA en un proveedor de nube.** Se reutilizan las mismas imágenes y variables de la instalación privada.

## Componentes y equivalentes administrados

| Componente | Imagen / servicio | En la nube |
|---|---|---|
| API | `gagetracker-api` (`backend/Dockerfile`), *health check* `/health/ready` | Contenedor con 2 o más réplicas detrás del balanceador |
| Worker | La misma imagen, `python -m app.worker` | **Una sola** réplica (los trabajos son idempotentes, pero así se evita trabajo duplicado) |
| Migraciones | La misma imagen, `alembic upgrade head` | Tarea previa a cada despliegue |
| Web | `gagetracker-web` (`frontend/Dockerfile`, `API_URL` en *build*) | Contenedor; la CDN es opcional |
| Base de datos | PostgreSQL 16 | Servicio administrado con respaldos automáticos y PITR |
| Documentos | Volumen (`STORAGE_DIR`) | Disco persistente compartido. **Pendiente**: almacenamiento de objetos S3/Blob, hoy no implementado |
| Secretos | `JWT_SECRET`, `SECRET_ENCRYPTION_KEY`, credenciales de BD | Gestor de secretos del proveedor, inyectados como variables |
| HTTPS | Caddy (privado) | Balanceador con certificado administrado |
| Logs | JSON por línea (`LOG_JSON=true`) | Recolector del proveedor; alertas por `status>=500` |
| Monitoreo | `/health/live`, `/health/ready` | Sondas de liveness y readiness; alerta si `database != ok` |

## Ambientes

`APP_ENV=production` activa la validación estricta de secretos y desactiva `/api/docs`. Use bases y almacenamiento separados por ambiente (desarrollo, staging, producción). La instancia demo vive en su propia base (`scripts/demo-reset.ps1`).

## Actualizaciones versionadas

Imágenes etiquetadas con la versión semántica (`GT_VERSION`). Procedimiento:
1. Respaldo o *snapshot* de la base.
2. Tarea de migración.
3. Despliegue gradual de la API.
4. Reinicio del *worker*.
5. Verificación de `/health/ready`.

*Rollback* como en `DEPLOYMENT_PRIVATE.md` §4.

## Multi-tenant en SaaS

Todas las organizaciones comparten la base; el aislamiento lo garantiza la aplicación y está probado en `test_tenant_isolation` y en las pruebas de cada módulo. **Pendiente** como defensa en profundidad: *Row Level Security* de PostgreSQL.
