# Modelo de datos

PostgreSQL 16. Esquema versionado con Alembic (`backend/alembic/versions/0001…0011`). Todas las tablas de negocio llevan `organization_id`; las consultas siempre filtran por organización y por alcance de planta (`TenantContext`).

## Principios

- **Multi-tenant**: cada registro pertenece a una organización. Un recurso de otra organización responde 404.
- **Trazabilidad**: `audit_events` registra quién, cuándo, qué entidad, acción, valores anteriores y nuevos (`changes`), motivo, request id e IP. Es de solo inserción por trigger.
- **Registros inmutables**:
  - Las historias de estado, las ejecuciones MSA, los reportes MSA, las lecturas de dispositivos y los eventos de workflow, de outbox y de webhooks no se pueden modificar ni borrar.
  - Las mediciones (puntos de calibración, resultados dimensionales, observaciones MSA) se corrigen con una fila que reemplaza a la anterior, que se conserva.
  - Las versiones de configuración y los criterios MSA aprobados no cambian su contenido.
- **Integridad**: claves foráneas con `ON DELETE RESTRICT`, restricciones `CHECK` para catálogos y fechas, y unicidades por organización (códigos de instrumento, de documento y de estudio).
- **Numeración**: `code_sequences` emite consecutivos por organización, prefijo y año con bloqueo de fila. Hay una prueba de concurrencia con 20 hilos.

## Relaciones principales

```
organizations ─┬─ plants ─ departments
               ├─ organization_memberships ─ users ─ roles ─ permissions
               ├─ gage_types ─ gages ─┬─ gage_status_history / gage_movements
               │                      ├─ calibration_activities ─┬─ calibration_points (As Found / As Left)
               │                      │                          ├─ calibration_certificates ─ attachments
               │                      │                          └─ calibration_standard_usages ─ standards ─ standard_certificates
               │                      ├─ msa_studies ─┬─ msa_observations
               │                      │               ├─ msa_runs ─ msa_criteria_sets (instantánea)
               │                      │               └─ msa_reports ─ attachments
               │                      ├─ oot_cases ─┬─ oot_impact_items / oot_actions
               │                      │             └─ calibration_activities (detección, última aceptable)
               │                      └─ devices ─ device_readings
               ├─ service_requests ─ work_orders ─┬─ inspection_results ─ gages
               │                                  └─ measurement_reports ─ attachments
               ├─ personnel_profiles / competencies / competency_records / authorizations
               ├─ config_items ─ config_versions;  custom_field_values;  workflow_events
               ├─ outbox_events ─ webhook_deliveries ─ webhook_attempts ← webhook_endpoints
               └─ api_clients (usuario de servicio) / api_request_log / import_jobs
```

## Mantenimiento

- Después de una restauración o de cargas masivas, ejecute `ANALYZE`. Sin estadísticas actualizadas, una consulta del tablero tardó 4.8 s en lugar de 0.09 s con 5 000 instrumentos. `scripts/restore.ps1` y `deploy/restore.sh` ya lo ejecutan.
- Las migraciones se prueban en cada corrida de pruebas en tres pasos: subida completa, bajada completa y nueva subida. `alembic check` compara el modelo con la base.

<!-- GENERATED -->

## Referencia de tablas (generada desde el código · revisión `0011_security` · 63 tablas)

Protección: `forbid_append_only_change` = solo inserción; `protect_measurement_row` = correcciones solo por reemplazo; `protect_config_version` / `protect_criteria_set` = contenido inmutable tras aprobación.


### Auditoría

| Tabla | Columnas | Relaciones (FK) | Protección en BD |
|---|---|---|---|
| `audit_events` | 11 | — | forbid_append_only_change |

### Calibration

| Tabla | Columnas | Relaciones (FK) | Protección en BD |
|---|---|---|---|
| `calibration_settings` | 11 | plant_id → plants | — |
| `calibration_activities` | 42 | gage_id → gages; plant_id → plants | — |
| `calibration_certificates` | 12 | attachment_id → attachments; calibration_id → calibration_activities; gage_id → gages | — |
| `calibration_points` | 18 | calibration_id → calibration_activities; supersedes_id → calibration_points | protect_measurement_row |
| `calibration_standard_usages` | 13 | calibration_id → calibration_activities; certificate_id → standard_certificates; standard_id → standards | — |
| `calibration_status_history` | 9 | calibration_id → calibration_activities | forbid_append_only_change |

### Competency

| Tabla | Columnas | Relaciones (FK) | Protección en BD |
|---|---|---|---|
| `competencies` | 9 | — | — |
| `competency_records` | 14 | competency_id → competencies | forbid_append_only_change |
| `authorizations` | 15 | competency_record_id → competency_records; gage_type_id → gage_types; plant_id → plants | — |
| `personnel_profiles` | 12 | department_id → departments; plant_id → plants | — |

### Configuración

| Tabla | Columnas | Relaciones (FK) | Protección en BD |
|---|---|---|---|
| `config_items` | 10 | — | — |
| `custom_field_values` | 9 | — | — |
| `workflow_events` | 14 | — | forbid_append_only_change |
| `config_versions` | 12 | item_id → config_items | protect_config_version |

### Documentos

| Tabla | Columnas | Relaciones (FK) | Protección en BD |
|---|---|---|---|
| `attachments` | 17 | — | — |

### Eventos

| Tabla | Columnas | Relaciones (FK) | Protección en BD |
|---|---|---|---|
| `outbox_events` | 8 | — | forbid_append_only_change |

### Gage Management

| Tabla | Columnas | Relaciones (FK) | Protección en BD |
|---|---|---|---|
| `gage_types` | 9 | — | — |
| `gages` | 31 | department_id → departments; gage_type_id → gage_types; plant_id → plants | — |
| `gage_movements` | 7 | gage_id → gages | forbid_append_only_change |
| `gage_status_history` | 10 | gage_id → gages | forbid_append_only_change |

### Integraciones

| Tabla | Columnas | Relaciones (FK) | Protección en BD |
|---|---|---|---|
| `idempotency_records` | 10 | — | — |
| `api_clients` | 12 | — | — |
| `webhook_endpoints` | 9 | — | — |
| `api_request_log` | 8 | client_id → api_clients | forbid_append_only_change |
| `import_jobs` | 19 | attachment_id → attachments; reprocess_of_id → import_jobs | — |
| `webhook_deliveries` | 11 | endpoint_id → webhook_endpoints; event_id → outbox_events | — |
| `webhook_attempts` | 7 | delivery_id → webhook_deliveries | forbid_append_only_change |
| `devices` | 11 | gage_id → gages; plant_id → plants | — |
| `device_readings` | 12 | device_id → devices; gage_id → gages | forbid_append_only_change |

### Laboratory

| Tabla | Columnas | Relaciones (FK) | Protección en BD |
|---|---|---|---|
| `lab_services` | 11 | — | — |
| `lab_settings` | 3 | — | — |
| `technician_absences` | 8 | — | — |
| `service_requests` | 23 | department_id → departments; plant_id → plants; service_id → lab_services | — |
| `work_orders` | 20 | plant_id → plants; service_id → lab_services; service_request_id → service_requests | — |
| `inspection_results` | 21 | gage_id → gages; supersedes_id → inspection_results; work_order_id → work_orders | protect_measurement_row |
| `measurement_reports` | 14 | attachment_id → attachments; work_order_id → work_orders | — |
| `work_order_equipment` | 2 | gage_id → gages; work_order_id → work_orders | — |
| `work_order_events` | 9 | work_order_id → work_orders | forbid_append_only_change |

### MSA

| Tabla | Columnas | Relaciones (FK) | Protección en BD |
|---|---|---|---|
| `msa_criteria_sets` | 17 | plant_id → plants | protect_criteria_set |
| `msa_studies` | 28 | criteria_set_id → msa_criteria_sets; department_id → departments; gage_id → gages; plant_id → plants | — |
| `msa_observations` | 19 | study_id → msa_studies; supersedes_id → msa_observations | protect_measurement_row |
| `msa_runs` | 18 | criteria_set_id → msa_criteria_sets; study_id → msa_studies | forbid_append_only_change |
| `msa_reports` | 8 | attachment_id → attachments; run_id → msa_runs; study_id → msa_studies | forbid_append_only_change |

### Notificaciones

| Tabla | Columnas | Relaciones (FK) | Protección en BD |
|---|---|---|---|
| `notification_preferences` | 5 | — | — |
| `notifications` | 9 | — | — |

### OOT

| Tabla | Columnas | Relaciones (FK) | Protección en BD |
|---|---|---|---|
| `oot_settings` | 7 | — | — |
| `oot_cases` | 41 | calibration_id → calibration_activities; gage_id → gages; last_acceptable_calibration_id → calibration_activities; plant_id → plants | — |
| `oot_actions` | 13 | case_id → oot_cases | — |
| `oot_impact_items` | 16 | case_id → oot_cases | — |

### Plataforma

| Tabla | Columnas | Relaciones (FK) | Protección en BD |
|---|---|---|---|
| `organizations` | 8 | — | — |
| `permissions` | 2 | — | — |
| `roles` | 6 | — | — |
| `users` | 10 | — | — |
| `code_sequences` | 5 | — | — |
| `organization_memberships` | 7 | role_id → roles | — |
| `password_reset_tokens` | 7 | — | — |
| `plants` | 7 | — | — |
| `role_permissions` | 2 | permission_code → permissions; role_id → roles | — |
| `departments` | 8 | plant_id → plants | — |
| `plant_memberships` | 2 | membership_id → organization_memberships; plant_id → plants | — |

### Standards

| Tabla | Columnas | Relaciones (FK) | Protección en BD |
|---|---|---|---|
| `standards` | 26 | current_certificate_id → standard_certificates; plant_id → plants | — |
| `standard_certificates` | 15 | attachment_id → attachments; standard_id → standards | — |
