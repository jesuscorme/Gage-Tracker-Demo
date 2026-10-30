# Decisiones de arquitectura (ADR)

Formato breve: contexto → decisión → consecuencias. Estado: **Aceptada** salvo indicación.

---

## ADR-001 · Monolito modular FastAPI + Next.js + PostgreSQL

**Contexto.** Repositorio vacío; el plan propone FastAPI/Next.js/PostgreSQL y prohíbe microservicios prematuros.
**Decisión.** Un backend FastAPI organizado por módulos de dominio (`app/modules/<módulo>` con `models`, `schemas`, `service`, `router`) y un frontend Next.js independiente. Un único esquema PostgreSQL.
**Consecuencias.** Despliegue simple (2 contenedores + BD), mismo artefacto para Cloud y Private. Los módulos se comunican por servicios Python, no por red. Las reglas de negocio viven en `service.py`; los routers son delgados.

## ADR-002 · Contexto de tenant explícito por request

**Contexto.** Un usuario puede pertenecer a varias organizaciones; cada request debe operar en una sola.
**Decisión.** La dependencia `require(*permisos)` resuelve usuario (Bearer) → organización (`X-Organization-Id`, o la única membresía) → permisos del rol → alcance de plantas. Todo servicio filtra por `ctx.organization_id` y valida plantas con `ctx.can_access_plant`. Recursos de otro tenant responden **404** (no se revela su existencia); usar una organización ajena en el header responde 403.
**Consecuencias.** El aislamiento depende de que cada consulta use `scoped_query`/filtros; está cubierto por `tests/test_tenant_isolation.py` (9 pruebas). Ver ADR-003.

## ADR-003 · Aislamiento en aplicación; RLS diferido

**Decisión.** Por ahora el aislamiento se implementa en la capa de servicio, con pruebas sistemáticas. PostgreSQL Row Level Security queda como mejora de defensa en profundidad (requiere rol de BD no propietario y `SET LOCAL app.org_id` por transacción).
**Estado.** Aceptada con revisión pendiente antes de producción (Fase 11).

## ADR-004 · Autenticación local JWT ahora, OIDC después

**Contexto.** El plan propone OIDC/OAuth2; no hay proveedor de identidad definido.
**Decisión.** Cuentas locales (bcrypt, contraseña ≥ 10 caracteres combinando letras y dígitos/símbolos, máx. 72 bytes) y tokens de acceso JWT HS256 de corta vida (60 min). El secreto es obligatorio en producción (la app no arranca con el valor de desarrollo). El modelo `users` es independiente del mecanismo, de modo que OIDC se puede añadir como otro proveedor.
**Consecuencias.** Sin refresh tokens ni revocación: al desactivar una membresía el acceso se corta de inmediato (se valida en cada request), pero el token sigue siendo válido para `/auth/me` hasta expirar.

## ADR-005 · RBAC por permisos con roles de sistema

**Decisión.** El backend comprueba **permisos** (`gages:release`, `audit:read`, …), no nombres de rol. Cinco roles de sistema sembrados por migración: `org_admin`, `metrology_manager`, `metrology_technician`, `auditor`, `viewer`. Una membresía = un rol por organización + lista opcional de plantas.
**Consecuencias.** Roles personalizados por organización (Fase 9) se agregan sin cambiar los endpoints. La prueba `test_seeded_roles_match_permission_catalogue` evita divergencias entre código y migraciones.

## ADR-006 · Estado del instrumento: controlado + calculado

**Decisión.** Se guarda `control_status` (`ACTIVE`, `OUT_OF_SERVICE`, `IN_CALIBRATION`, `INACTIVE`), que solo cambia mediante transiciones autorizadas. El estado visible se **calcula** al vuelo:

| Condición (control = ACTIVE) | Estado |
|---|---|
| Sin fecha de calibración | Overdue |
| `next_due_date < hoy` | Overdue |
| `hoy ≤ next_due_date ≤ hoy + ventana` | Due Soon |
| resto | Calibrated |

Si `control_status ≠ ACTIVE`, ese valor es el estado. "Hoy" se evalúa en la zona horaria de la organización; la ventana `due_soon_days` es configurable (default 30). Solo Calibrated y Due Soon están **disponibles para uso**.
La regla existe en Python y como expresión SQL (para filtros/conteos); `tests/test_gage_status.py` verifica que coincidan.

**Reglas de autorización:**
- Restringir (→ Out of Service / In Calibration) requiere `gages:restrict`; **liberar** (→ ACTIVE) requiere `gages:release`; dar de baja requiere `gages:retire`.
- La edición general (`PATCH`) no puede modificar `control_status` ni el Gage ID (rechazo 422).
- Cambiar `last_calibration_date` o `calibration_frequency_days` mueve el vencimiento (puede convertir un Overdue en Calibrated), por eso exige `gages:release`.
- Liberar no omite el vencimiento: un instrumento vencido liberado sigue Overdue.
- Al liberar desde In Calibration puede registrarse la fecha de calibración (provisional hasta Fase 3; no futura ni anterior a la última).

## ADR-007 · Audit trail append-only en la misma transacción

**Decisión.** `audit_events` y `gage_status_history` se escriben en la misma transacción que el cambio de negocio (no hay registros huérfanos ni cambios sin auditoría). Un trigger PostgreSQL rechaza `UPDATE`/`DELETE` en ambas tablas. Las marcas de tiempo usan `clock_timestamp()` para reflejar el orden real dentro de una transacción. Se guardan diffs `{campo: [antes, después]}`, actor, motivo, IP e `request_id`.
**Consecuencias.** Los intentos de login fallidos se registran sin organización (eventos de plataforma, no visibles para tenants).

## ADR-008 · Baja lógica

**Decisión.** "Eliminar" un instrumento es la transición a `INACTIVE` con motivo obligatorio (`retired_at` registrado). No hay `DELETE` físico en la API. Los instrumentos inactivos se ocultan por defecto en listados, no se pueden editar y pueden reactivarse con `gages:release`.

## ADR-009 · Frontend con proxy same-origin y i18n propio

**Decisión.** El navegador llama a `/api/*` en el mismo origen; Next.js reescribe hacia el backend (`API_URL`). Evita CORS y exponer el backend. El token se guarda en `sessionStorage` (riesgo XSS aceptado temporalmente; ver ADR-004). i18n con diccionarios tipados `es`/`en` (TypeScript falla si falta una clave); preferencia en `localStorage`. Los nombres de estado (Calibrated, Due Soon…) se mantienen en inglés en ambos idiomas por ser la terminología solicitada.
**Consecuencias.** Las reescrituras se fijan en `next build`: `API_URL` debe definirse al construir.

## ADR-010 · Decimales y unicidad

- Rango y resolución: `NUMERIC(18,6)`; viajan como texto en JSON para no perder precisión; la exactitud es texto libre (±0.02 mm, % FS, clase).
- Gage ID: normalizado a mayúsculas, único por organización mediante restricción de BD. La regla configurable (por planta) queda pendiente.

## ADR-011 · Base de datos de desarrollo sin Docker

**Contexto.** La máquina de desarrollo no tiene Docker y la instancia PostgreSQL existente usa credenciales no disponibles.
**Decisión.** `scripts/dev-db.ps1` crea un cluster privado con los binarios de PostgreSQL 16 en `.local/pgdata` (puerto 5433, autenticación `trust` solo en localhost). `docker-compose.yml` expone la BD en el mismo puerto para que `.env` sea idéntico en ambos modos.
**Consecuencias.** Solo para desarrollo; nunca usar `trust` en servidores compartidos.

---

# Segundo bloque (Fases 2–5)

## ADR-012 · Documentos: metadatos en BD, binarios fuera, acceso por registro dueño

Archivos validados por contenido (firma de bytes) y extensión: PDF, PNG, JPEG, WEBP, XLSX, CSV; máx. 20 MB (`MAX_UPLOAD_MB`). Se guardan con clave aleatoria y escritura exclusiva (`open(..., "x")`): no se sobrescriben. La tabla `attachments` guarda hash SHA-256, tamaño, tipo, autor. El permiso para ver/subir un archivo es el del registro al que pertenece (registro de tipos por módulo); fuera del tenant responde 404. El retiro es lógico con motivo; los documentos que respaldan registros aprobados (certificados, informes, evidencias liberadas) quedan **bloqueados**. Hoy el almacenamiento es disco local (`STORAGE_DIR`); la interfaz `LocalStorage.put/get` permite sustituirlo por S3-compatible.

## ADR-013 · Asignación y fechas del instrumento por operaciones controladas

- `PATCH /gages` solo cambia datos descriptivos (`extra="forbid"`).
- Planta, departamento, ubicación y responsable se cambian con `/transfer` (permiso `gages:transfer`, motivo obligatorio, historial `gage_movements`).
- `last_calibration_date` solo al alta/importación (registro inicial de inventario existente); después la actualiza **únicamente** la liberación de una calibración. Se retiró la fecha manual del primer bloque (ADR-006 actualizado).
- Una calibración liberada más antigua que la última registrada no retrocede el vencimiento.

## ADR-014 · Flujo de calibración, segregación de funciones y liberación transaccional

Estados y permisos por etapa (`calibration:manage|execute|review|approve|release`). Además del permiso RBAC, ejecutar calibraciones internas/verificaciones, revisar y aprobar exige **autorización personal vigente** (ADR-016). Revisor ≠ ejecutor; aprobador ≠ ejecutor y ≠ revisor. Requisitos de evidencia configurables por tipo y planta (`calibration_settings`), revalidados al liberar. La liberación, la actualización del instrumento (fechas y estado), el historial de estado y la auditoría ocurren en **una sola transacción**. Resultado no conforme ⇒ instrumento Out of Service. La verificación de rutina registra `last_verification_date` y no mueve el vencimiento de calibración. Mientras una calibración retiene el instrumento (In Calibration), la liberación manual se bloquea (`release_guards`).

## ADR-015 · Resultados de medición inmutables (sustitución)

As Found / As Left y resultados dimensionales son filas nuevas; una corrección crea otra fila con `supersedes_id` y motivo, y marca la original como sustituida. Un trigger (`protect_measurement_row`) solo permite cambiar `superseded` de falso a verdadero; cualquier otra modificación o borrado falla en la base de datos.

## ADR-016 · Autorizaciones de competencia como segunda llave

Las autorizaciones (`authorizations`) son por persona, actividad (`INTERNAL_CALIBRATION`, `ROUTINE_VERIFICATION`, `TECHNICAL_REVIEW`, `APPROVAL`, `LAB_SERVICE`, `DIMENSIONAL_INSPECTION`, `MSA_EVALUATION`), con alcance opcional por tipo de instrumento y planta y vigencia. No se editan: se revocan con motivo y se otorgan de nuevo. `ensure_authorized` es la única verificación usada por Calibración y Laboratorio. Los requisitos normativos concretos (qué formación habilita qué actividad) **no** están codificados: los define el cliente al otorgar autorizaciones con su fundamento.

## ADR-017 · Patrones: vigencia, excepción documentada e instantánea de uso

Un patrón solo es utilizable si está Vigente o Por vencer en la fecha de ejecución. Otro estado exige motivo y permiso `standards:exception`; queda auditado en la actividad y en el patrón. Cada uso guarda estado, certificado y vigencia de ese momento, de modo que la trazabilidad no cambia aunque el patrón cambie después.

## ADR-018 · Programación de laboratorio con reglas de compatibilidad

La asignación de OT rechaza: técnico sin autorización vigente para el servicio, ausencias, traslape con otra OT del técnico, equipo no disponible, equipo que vence antes del fin del trabajo y equipo reservado en otra OT traslapada. Las mediciones solo se aceptan con equipo asignado y disponible en ese momento; el estado del equipo se guarda con cada medición. Los informes son instantáneas congeladas con PDF (fpdf2, fuentes Latin-1); la reemisión crea revisión nueva con motivo.

## ADR-019 · Notificaciones en la aplicación y alertas calculadas

Las notificaciones se crean en la misma transacción que el evento y respetan preferencias por usuario (opt-out). Las alertas (vencidos, por vencer, patrones, autorizaciones, OT atrasadas) se calculan al consultar, sin tareas programadas. Correo y tareas programadas quedan para la fase de integraciones.

## ADR-020 · Numeración de documentos

`CAL-AAAA-NNNNN`, `SR-…`, `WO-…`, `MR-…` por organización y año, con fila bloqueada (`code_sequences`), sin huecos por concurrencia.

## ADR-021 · Motor estadístico independiente, un módulo por método

`backend/app/engine/` no importa nada de la API ni de la BD: JSON de entrada → JSON de salida. Cada método tiene su propio módulo, validación, modelo y versión (no hay una fórmula genérica). Constantes solo de tablas publicadas; fuera de rango el diseño se rechaza en lugar de extrapolar. numpy/scipy para el cálculo; statsmodels/pandas solo en pruebas como implementación independiente.

## ADR-022 · Ejecuciones MSA inmutables y reproducibles

Cada cálculo guarda la instantánea exacta de entrada, su SHA-256, versión del algoritmo y del motor, instantánea de criterios, resultados y decisión (`msa_runs`, trigger append-only). Una actualización del motor nunca reescribe resultados: `verify` recalcula y compara sin modificar. Los reportes PDF se generan desde la instantánea de la ejecución.

## ADR-023 · Resultado estadístico separado de la decisión

El motor no decide aceptación. Los criterios son datos de la organización (alcance organización/planta/cliente, fuente, versión, segundo aprobador; inmutables tras aprobarse). Sin criterios → `NO_CRITERIA`; indicador no calculable → `INCONCLUSIVE`. La conclusión final la registra una persona con justificación si difiere.

## ADR-024 · Configuración versionada con aprobación

`config_items` + `config_versions` (contenido inmutable por trigger). Workflows, matrices de aprobación y reglas requieren aprobación de otro usuario; campos y formularios se activan al guardar. Definiciones declarativas validadas: sin código ni expresiones regulares de usuarios (formatos de texto de una lista cerrada).

## ADR-025 · Motor de workflow genérico con versión fijada por registro

Cada registro conserva la versión del workflow con la que nació (0 = definición del sistema). Estados del sistema obligatorios por entidad; capacidades por estado que el dominio consulta (p. ej. `capture`, `release_gage`). Transición = estado + permiso + matriz + autorización personal + segregación + comentario + reglas + precondiciones del dominio; votos para quórum; escalamiento idempotente. Historial append-only.

## ADR-026 · OOT acoplado por hooks

Calibración expone `release_hooks`; Gage Management `restriction_holders` y `release_guards`. OOT los usa para crear el caso en la misma transacción de la liberación, mantener el instrumento fuera de servicio aunque se recalibre, y bloquear la liberación ordinaria. Solo `oot:approve` + `gages:release` liberan, y con una calibración aceptable posterior a la detección.

## ADR-027 · Outbox transaccional + webhooks; idempotencia por middleware

Eventos en la misma transacción del cambio (deduplicación por clave). Entrega asíncrona firmada (HMAC), backoff y dead letter. Idempotencia de escrituras por `Idempotency-Key`, con alcance por credencial y organización, guardando la respuesta 24 h.

## ADR-028 · Clientes API como cuentas de servicio; conectores por adaptador

Una llave API resuelve a un usuario de servicio con membresía: todas las reglas de permisos, plantas, tenant y auditoría se aplican sin código especial. Los dispositivos se integran por adaptadores; el servidor re-interpreta la trama cruda. No se declara compatibilidad con fabricantes sin adaptador probado.

## ADR-029 · Tablero y reportes sobre consultas vivas y conciliadas

El tablero y los reportes consultan las tablas operativas en cada petición (sin agregados precalculados). Todas las cifras de instrumentos parten de la misma población filtrada, de modo que las particiones (por estado, tipo, planta) suman el total y coinciden con los listados; las pruebas lo verifican. Si en el futuro se requiere caché, debe conservar esta conciliación.

## ADR-030 · Revocación de sesiones por versión de token

En lugar de una lista de tokens revocados, cada usuario tiene `token_version` incluido en el JWT. Cerrar sesión en todos los dispositivos, cambiar o restablecer la contraseña incrementa la versión e invalida todo lo emitido. Restablecimiento por enlace de un solo uso emitido por un administrador (sin SMTP todavía).

## ADR-031 · Worker dedicado en producción

Los trabajos de fondo (webhooks, escalamientos, vencidos) son idempotentes y corren en `python -m app.worker`; la API se despliega con `SCHEDULER_ENABLED=false`. El hilo dentro de la API queda para instalaciones de un solo proceso.

## ADR-032 · Actualización de dependencias por seguridad

FastAPI 0.115 → 0.162 (starlette 1.10) para cerrar avisos publicados; se aceptó el salto porque las 234 pruebas de backend y las 43 E2E pasan sin cambios de código. `postcss` se fuerza con `overrides` dentro de Next 15 hasta migrar a Next 16. La auditoría de dependencias forma parte del CI.
