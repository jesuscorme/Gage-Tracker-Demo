# Arquitectura

## Vista general

```
Navegador (Next.js 15, React 19, TypeScript; ES/EN)
        │  same-origin /api  (rewrite)
        ▼
Proxy HTTPS (Caddy) ──► Web (next start)
        │
        └──────────────► API FastAPI (monolito modular, Python 3.12)
                              │  SQLAlchemy 2 / Alembic
                              ▼
                         PostgreSQL 16  ◄──── Worker (python -m app.worker)
                              │                 webhooks · escalamientos · vencidos
                         Almacenamiento de documentos (volumen / carpeta, SHA-256)

Edge Connector (red de planta) ──HTTPS + X-API-Key──► /api/v1/connectors/readings
Sistemas externos (ERP, MES) ──X-API-Key / webhooks firmados──► /api/v1/exchange, /webhooks
```

## Módulos del backend (`backend/app/modules`)

| Módulo | Responsabilidad |
|---|---|
| identity / organizations | Usuarios, organizaciones, plantas, departamentos, roles, permisos, sesiones, contraseñas |
| audit | Bitácora inmutable y consulta |
| documents | Adjuntos con control de acceso según el registro dueño |
| gages | Inventario, estados (controlado y calculado), transferencias, importación y exportación |
| calibration | Planificación → liberación, As Found / As Left, certificados, ajustes por planta |
| standards / competency | Patrones y certificados; perfiles, competencias, autorizaciones |
| laboratory | Solicitudes, programación, OT, mediciones, informes, KPIs |
| msa + `app/engine` | Estudios, captura, criterios, ejecuciones versionadas, reportes. Motor estadístico independiente |
| oot | Casos, restricción, análisis retrospectivo, acciones, cierre |
| configuration | Configuración versionada: campos, formularios, workflows, matrices, reglas |
| events / integrations | Outbox, webhooks, clientes API, idempotencia, importaciones, conectores, contratos de intercambio |
| compliance | Capa de evidencias sobre los datos existentes |
| dashboard / reports | Tablero ejecutivo conciliado; centro de reportes PDF, Excel y CSV |
| notifications | Notificaciones en la aplicación |

Acoplamiento entre módulos mediante *hooks* explícitos (`release_guards`, `restriction_holders`, `release_hooks`, registros de documentos, workflows e importadores). Así, por ejemplo, OOT reacciona a la liberación de una calibración sin que Calibración dependa de OOT.

## Decisiones clave

Ver `ARCHITECTURE_DECISIONS.md` (ADR-001 … ADR-032). Las principales:
- monolito modular;
- multi-tenant por columna con contexto obligatorio;
- registros inmutables protegidos por triggers;
- motor estadístico versionado e independiente;
- outbox transaccional;
- clientes API como cuentas de servicio;
- *worker* separado en producción.

## Frontend (`frontend/src`)

- App Router con un *shell* común (navegación por permisos, selector de organización, idioma, notificaciones).
- Cliente API con token en `sessionStorage` y cabecera de organización.
- i18n tipado: cada clave existe en ES y EN, y la compilación falla si falta una traducción.
- Componentes propios: tablas, gráficas SVG sin dependencias, modales, panel de workflow, campos personalizados.

## Despliegue

`deploy/docker-compose.yml`: servicios db, migrate, api, worker, web y proxy. Ver `DEPLOYMENT_PRIVATE.md` y `DEPLOYMENT_CLOUD.md`.
