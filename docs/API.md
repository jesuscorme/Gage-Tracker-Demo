# API

Base: `/api/v1`. Documentación interactiva OpenAPI en `/api/docs` (desactivada cuando `APP_ENV=production`).

## Convenciones

| Tema | Regla |
|---|---|
| Autenticación | Usuarios: `Authorization: Bearer <JWT>`, obtenido con `POST /auth/login`. Sistemas: `X-API-Key: gtk_<prefijo>_<secreto>`, que funciona como una cuenta de servicio con rol y plantas. |
| Organización | `X-Organization-Id` cuando el usuario pertenece a varias. |
| Autorización | Permisos del rol (48) + alcance de planta + autorización personal para actividades técnicas + matriz de aprobación configurable. |
| Errores | `{"error": {"code", "message", "details", "request_id"}}`. Códigos: 401, 403, 404 (también para recursos de otra organización), 409, 422, 429 (bloqueo por intentos), 500 (sin detalles internos). |
| Paginación | Listados grandes: `page`, `page_size`. Contratos de intercambio: `{items, page, page_size, total, next_page}`. |
| Idempotencia | `Idempotency-Key` en POST/PUT/PATCH: la respuesta se guarda 24 h y se repite sin volver a ejecutar. |
| Versionado | `/api/v1`. Los contratos `/exchange/{recurso}` declaran `X-Contract-Version: 1`. |
| Seguridad | Cabeceras `X-Content-Type-Options`, `X-Frame-Options`, `Content-Security-Policy` y HSTS detrás de HTTPS. |

Integraciones (llaves, webhooks, importaciones, conectores): ver `docs/integrations/README.md`.

<!-- GENERATED -->

## Inventario de endpoints (generado desde OpenAPI · 208 operaciones · versión 1.0.0rc1)


### audit

| Método | Ruta | Descripción |
|---|---|---|
| GET | `/api/v1/audit-events` |  |

### auth

| Método | Ruta | Descripción |
|---|---|---|
| POST | `/api/v1/auth/change-password` |  |
| POST | `/api/v1/auth/login` |  |
| POST | `/api/v1/auth/logout-all` | Revoke every token issued to the user (all devices). |
| GET | `/api/v1/auth/me` |  |
| PATCH | `/api/v1/auth/me` |  |
| POST | `/api/v1/auth/register` | Create a new organization, its first plant and its first administrator. |
| POST | `/api/v1/auth/reset-password` |  |

### calibration

| Método | Ruta | Descripción |
|---|---|---|
| GET | `/api/v1/calibration-settings` |  |
| PUT | `/api/v1/calibration-settings` |  |
| GET | `/api/v1/calibrations` |  |
| POST | `/api/v1/calibrations` |  |
| GET | `/api/v1/calibrations/calendar` |  |
| GET | `/api/v1/calibrations/overview` |  |
| GET | `/api/v1/calibrations/{activity_id}` |  |
| PATCH | `/api/v1/calibrations/{activity_id}` |  |
| POST | `/api/v1/calibrations/{activity_id}/approve` |  |
| POST | `/api/v1/calibrations/{activity_id}/cancel` |  |
| POST | `/api/v1/calibrations/{activity_id}/certificates` |  |
| POST | `/api/v1/calibrations/{activity_id}/points` |  |
| POST | `/api/v1/calibrations/{activity_id}/release` |  |
| POST | `/api/v1/calibrations/{activity_id}/request` |  |
| POST | `/api/v1/calibrations/{activity_id}/review` |  |
| POST | `/api/v1/calibrations/{activity_id}/schedule` |  |
| POST | `/api/v1/calibrations/{activity_id}/standards` |  |
| POST | `/api/v1/calibrations/{activity_id}/standards/{usage_id}/remove` |  |
| POST | `/api/v1/calibrations/{activity_id}/start` |  |
| POST | `/api/v1/calibrations/{activity_id}/submit` |  |
| GET | `/api/v1/gages/{gage_id}/calibration-summary` |  |
| GET | `/api/v1/standards/{standard_id}/usages` | Which activities used the standard, its condition and certificate on that date. |

### competency

| Método | Ruta | Descripción |
|---|---|---|
| GET | `/api/v1/competency/authorizations` |  |
| POST | `/api/v1/competency/authorizations` |  |
| POST | `/api/v1/competency/authorizations/{authorization_id}/revoke` |  |
| GET | `/api/v1/competency/authorized-users` | People with a current authorization (for assignment pickers). |
| GET | `/api/v1/competency/competencies` |  |
| POST | `/api/v1/competency/competencies` |  |
| PATCH | `/api/v1/competency/competencies/{competency_id}` |  |
| GET | `/api/v1/competency/matrix` |  |
| GET | `/api/v1/competency/people` | Every active member, with their profile (if any) and current authorizations. |
| PUT | `/api/v1/competency/people/{user_id}` |  |
| GET | `/api/v1/competency/records` |  |
| POST | `/api/v1/competency/records` |  |

### compliance

| Método | Ruta | Descripción |
|---|---|---|
| GET | `/api/v1/compliance/approvals` |  |
| GET | `/api/v1/compliance/certificates` |  |
| GET | `/api/v1/compliance/clauses` |  |
| GET | `/api/v1/compliance/clauses/{standard}/{number}` |  |
| GET | `/api/v1/compliance/export.xlsx` |  |
| GET | `/api/v1/compliance/gages/{gage_id}/dossier` |  |
| GET | `/api/v1/compliance/matrix` |  |
| GET | `/api/v1/compliance/pending` |  |
| GET | `/api/v1/compliance/processes/{code}` |  |

### configuration

| Método | Ruta | Descripción |
|---|---|---|
| GET | `/api/v1/config/catalogue` |  |
| GET | `/api/v1/config/items` |  |
| POST | `/api/v1/config/items` |  |
| POST | `/api/v1/config/items/{item_id}/retire` |  |
| GET | `/api/v1/config/items/{item_id}/versions` |  |
| POST | `/api/v1/config/versions/{version_id}/approve` |  |
| POST | `/api/v1/config/versions/{version_id}/reject` |  |
| GET | `/api/v1/custom-fields/{entity_type}` |  |
| GET | `/api/v1/custom-fields/{entity_type}/{entity_id}` |  |
| PUT | `/api/v1/custom-fields/{entity_type}/{entity_id}` |  |
| GET | `/api/v1/forms/{entity_type}` |  |
| POST | `/api/v1/workflows/escalations/run` |  |
| GET | `/api/v1/workflows/{entity_type}/definition` |  |
| GET | `/api/v1/workflows/{entity_type}/{entity_id}` |  |
| POST | `/api/v1/workflows/{entity_type}/{entity_id}/transitions` |  |

### dashboard

| Método | Ruta | Descripción |
|---|---|---|
| GET | `/api/v1/dashboard/overview` | Executive dashboard. Filters apply to the gage population; out-of-scope plants are not found. |
| GET | `/api/v1/dashboard/summary` | Gage KPIs computed live from the gage table, within the user's plant scope. |

### documents

| Método | Ruta | Descripción |
|---|---|---|
| GET | `/api/v1/attachments` |  |
| POST | `/api/v1/attachments` | Generic upload. Certificates of calibrations/standards use their own endpoints. |
| GET | `/api/v1/attachments/{attachment_id}/download` |  |
| POST | `/api/v1/attachments/{attachment_id}/remove` |  |

### gages

| Método | Ruta | Descripción |
|---|---|---|
| GET | `/api/v1/gage-types` |  |
| POST | `/api/v1/gage-types` |  |
| PATCH | `/api/v1/gage-types/{type_id}` |  |
| GET | `/api/v1/gages` |  |
| POST | `/api/v1/gages` |  |
| GET | `/api/v1/gages/export` | Inventory export with the same filters as the list (scope-limited). |
| POST | `/api/v1/gages/import` |  |
| GET | `/api/v1/gages/import/template` |  |
| GET | `/api/v1/gages/{gage_id}` |  |
| PATCH | `/api/v1/gages/{gage_id}` |  |
| GET | `/api/v1/gages/{gage_id}/audit` | Change history of one gage (readable by anyone who can read the gage). |
| GET | `/api/v1/gages/{gage_id}/movements` |  |
| GET | `/api/v1/gages/{gage_id}/status-history` |  |
| POST | `/api/v1/gages/{gage_id}/transfer` | Reassign responsible and/or move to another plant, department or location. |
| POST | `/api/v1/gages/{gage_id}/transitions` | Change the controlled status. The required permission depends on the transition. |

### health

| Método | Ruta | Descripción |
|---|---|---|
| GET | `/health/live` | The process is up. |
| GET | `/health/ready` | The API can serve traffic: database reachable and migrated. |

### integrations

| Método | Ruta | Descripción |
|---|---|---|
| POST | `/api/v1/connectors/readings` |  |
| GET | `/api/v1/exchange/{resource}` |  |
| GET | `/api/v1/integrations/adapters` |  |
| GET | `/api/v1/integrations/api-clients` |  |
| POST | `/api/v1/integrations/api-clients` |  |
| GET | `/api/v1/integrations/api-clients/{client_id}/activity` |  |
| POST | `/api/v1/integrations/api-clients/{client_id}/revoke` |  |
| GET | `/api/v1/integrations/devices` |  |
| POST | `/api/v1/integrations/devices` |  |
| PUT | `/api/v1/integrations/devices/{device_id}/gage` |  |
| GET | `/api/v1/integrations/devices/{device_id}/readings` |  |
| POST | `/api/v1/integrations/devices/{device_id}/simulate` |  |
| GET | `/api/v1/integrations/event-types` |  |
| GET | `/api/v1/integrations/events` |  |
| GET | `/api/v1/integrations/importers` |  |
| GET | `/api/v1/integrations/importers/{code}/template` |  |
| GET | `/api/v1/integrations/imports` |  |
| POST | `/api/v1/integrations/imports` |  |
| GET | `/api/v1/integrations/imports/{job_id}` |  |
| POST | `/api/v1/integrations/imports/{job_id}/commit` |  |
| POST | `/api/v1/integrations/imports/{job_id}/reprocess` |  |
| GET | `/api/v1/integrations/webhook-deliveries` |  |
| GET | `/api/v1/integrations/webhook-deliveries/{delivery_id}/attempts` |  |
| POST | `/api/v1/integrations/webhook-deliveries/{delivery_id}/retry` |  |
| GET | `/api/v1/integrations/webhooks` |  |
| POST | `/api/v1/integrations/webhooks` |  |
| POST | `/api/v1/integrations/webhooks/dispatch` | Run fan-out and delivery now for this organization (the scheduler does it periodically). |
| POST | `/api/v1/integrations/webhooks/{endpoint_id}/activate` |  |
| POST | `/api/v1/integrations/webhooks/{endpoint_id}/deactivate` |  |

### laboratory

| Método | Ruta | Descripción |
|---|---|---|
| GET | `/api/v1/lab/absences` |  |
| POST | `/api/v1/lab/absences` |  |
| GET | `/api/v1/lab/dashboard` |  |
| GET | `/api/v1/lab/reports` |  |
| GET | `/api/v1/lab/reports/{report_id}` |  |
| GET | `/api/v1/lab/requests` |  |
| POST | `/api/v1/lab/requests` |  |
| GET | `/api/v1/lab/requests/{request_id}` |  |
| POST | `/api/v1/lab/requests/{request_id}/cancel` |  |
| POST | `/api/v1/lab/requests/{request_id}/decision` |  |
| GET | `/api/v1/lab/services` |  |
| POST | `/api/v1/lab/services` |  |
| PATCH | `/api/v1/lab/services/{service_id}` |  |
| GET | `/api/v1/lab/settings` |  |
| PUT | `/api/v1/lab/settings` |  |
| GET | `/api/v1/lab/work-orders` |  |
| POST | `/api/v1/lab/work-orders` |  |
| GET | `/api/v1/lab/work-orders/{wo_id}` |  |
| POST | `/api/v1/lab/work-orders/{wo_id}/cancel` |  |
| POST | `/api/v1/lab/work-orders/{wo_id}/complete` |  |
| POST | `/api/v1/lab/work-orders/{wo_id}/reports` |  |
| POST | `/api/v1/lab/work-orders/{wo_id}/results` |  |
| POST | `/api/v1/lab/work-orders/{wo_id}/schedule` |  |
| POST | `/api/v1/lab/work-orders/{wo_id}/start` |  |

### msa

| Método | Ruta | Descripción |
|---|---|---|
| GET | `/api/v1/msa/criteria` |  |
| POST | `/api/v1/msa/criteria` |  |
| GET | `/api/v1/msa/criteria/templates` |  |
| POST | `/api/v1/msa/criteria/{criteria_id}/approve` |  |
| POST | `/api/v1/msa/criteria/{criteria_id}/retire` |  |
| GET | `/api/v1/msa/methods` |  |
| POST | `/api/v1/msa/observations/{obs_id}/correct` |  |
| GET | `/api/v1/msa/runs/{run_id}` |  |
| POST | `/api/v1/msa/runs/{run_id}/verify` |  |
| GET | `/api/v1/msa/studies` |  |
| POST | `/api/v1/msa/studies` |  |
| GET | `/api/v1/msa/studies/{study_id}` |  |
| PATCH | `/api/v1/msa/studies/{study_id}` |  |
| POST | `/api/v1/msa/studies/{study_id}/calculate` |  |
| POST | `/api/v1/msa/studies/{study_id}/conclusion` |  |
| GET | `/api/v1/msa/studies/{study_id}/custom-fields` |  |
| GET | `/api/v1/msa/studies/{study_id}/observations` |  |
| POST | `/api/v1/msa/studies/{study_id}/observations` |  |
| GET | `/api/v1/msa/studies/{study_id}/reports` |  |
| POST | `/api/v1/msa/studies/{study_id}/reports` |  |
| GET | `/api/v1/msa/studies/{study_id}/runs` |  |
| GET | `/api/v1/msa/studies/{study_id}/sequence` |  |
| GET | `/api/v1/msa/studies/{study_id}/validation` |  |
| GET | `/api/v1/msa/studies/{study_id}/workflow` |  |

### notifications

| Método | Ruta | Descripción |
|---|---|---|
| GET | `/api/v1/alerts` | Live alert counters for the header, limited to what the user may see. |
| GET | `/api/v1/notifications` |  |
| GET | `/api/v1/notifications/preferences` |  |
| PUT | `/api/v1/notifications/preferences` |  |
| POST | `/api/v1/notifications/read` | Mark the given notifications (or all) as read. |

### oot

| Método | Ruta | Descripción |
|---|---|---|
| POST | `/api/v1/oot/actions/{action_id}/finish` |  |
| GET | `/api/v1/oot/cases` |  |
| POST | `/api/v1/oot/cases` |  |
| GET | `/api/v1/oot/cases/{case_id}` |  |
| PATCH | `/api/v1/oot/cases/{case_id}` |  |
| GET | `/api/v1/oot/cases/{case_id}/actions` |  |
| POST | `/api/v1/oot/cases/{case_id}/actions` |  |
| POST | `/api/v1/oot/cases/{case_id}/analysis` |  |
| GET | `/api/v1/oot/cases/{case_id}/calibration-history` |  |
| GET | `/api/v1/oot/cases/{case_id}/items` |  |
| POST | `/api/v1/oot/cases/{case_id}/items` |  |
| POST | `/api/v1/oot/cases/{case_id}/release-gage` |  |
| POST | `/api/v1/oot/items/{item_id}/assess` |  |
| GET | `/api/v1/oot/settings` |  |
| PUT | `/api/v1/oot/settings` |  |

### organization

| Método | Ruta | Descripción |
|---|---|---|
| GET | `/api/v1/departments` |  |
| POST | `/api/v1/departments` |  |
| PATCH | `/api/v1/departments/{department_id}` |  |
| GET | `/api/v1/organization` |  |
| PATCH | `/api/v1/organization` |  |
| GET | `/api/v1/plants` |  |
| POST | `/api/v1/plants` |  |
| PATCH | `/api/v1/plants/{plant_id}` |  |

### reports

| Método | Ruta | Descripción |
|---|---|---|
| GET | `/api/v1/reports` |  |
| GET | `/api/v1/reports/{key}` |  |

### standards

| Método | Ruta | Descripción |
|---|---|---|
| GET | `/api/v1/standards` |  |
| POST | `/api/v1/standards` |  |
| GET | `/api/v1/standards/{standard_id}` |  |
| PATCH | `/api/v1/standards/{standard_id}` |  |
| GET | `/api/v1/standards/{standard_id}/certificates` |  |
| POST | `/api/v1/standards/{standard_id}/certificates` |  |
| POST | `/api/v1/standards/{standard_id}/transitions` |  |

### users

| Método | Ruta | Descripción |
|---|---|---|
| GET | `/api/v1/roles` |  |
| GET | `/api/v1/users` |  |
| POST | `/api/v1/users` |  |
| PATCH | `/api/v1/users/{user_id}` |  |
| POST | `/api/v1/users/{user_id}/password-reset` | One-time reset token for a member (delivered by the administrator; shown once). |
