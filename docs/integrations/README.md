# Integraciones y datos

## 1. API versionada (`/api/v1`)

- **Autenticación**: usuarios con `Authorization: Bearer <JWT>`; sistemas con `X-API-Key: gtk_<prefijo>_<secreto>`. Un cliente API es una cuenta de servicio con su propia membresía: rol (`viewer`, `auditor`, `requester`, `metrology_technician`, `lab_technician`, `edge_agent`; nunca `org_admin`), alcance por planta y caducidad opcional. Solo se guarda el SHA-256 de la llave, que se muestra una única vez. Se puede revocar.
- **Autorización y tenant**: las mismas reglas que para usuarios (permisos del rol, plantas, aislamiento por organización; un recurso ajeno responde 404).
- **Registro de actividad**: cada llamada con llave queda en `api_request_log` (método, ruta, request id, IP); consulta en `GET /integrations/api-clients/{id}/activity`.
- **Errores**: siempre `{"error": {"code", "message", "details", "request_id"}}`.
- **Idempotencia**: cabecera `Idempotency-Key` (1–100 caracteres) en POST/PUT/PATCH. El primer resultado (2xx o 4xx) se guarda 24 h y una repetición idéntica lo devuelve con `Idempotent-Replayed: true` sin volver a ejecutar. Reusar la llave con otro cuerpo da 422 `idempotency_key_reused`; una repetición mientras la primera sigue en curso da 409. Un 5xx no se guarda, así que se puede reintentar.
- **Documentación OpenAPI**: `/api/docs` y `/api/openapi.json` (fuera de producción).

### Contratos de intercambio v1 (solo lectura)

`GET /api/v1/exchange/{recurso}?page=&page_size=(≤500)&updated_since=&status=&gage_id=` → `{contract_version, resource, items, page, page_size, total, next_page}` y cabecera `X-Contract-Version: 1`. Los campos de cada contrato son una lista explícita (ver `backend/app/modules/integrations/exchange.py`), independiente de los modelos internos. Cambiar un contrato significa publicar v2.

| Recurso | Permiso | Campos principales |
|---|---|---|
| `gages` | gages:read | id, gage_code, description, plant_id, control_status, status (calculado), last_calibration_date, next_due_date, updated_at |
| `calibrations` | calibration:read | calibration_code, gage_id, activity_type, status, performed_date, result, as_found/as_left_in_tolerance, due_date, released_at |
| `service-requests` | lab:read | request_code, customer, part_number, priority, requested/committed_date, status |
| `work-orders` | lab:read | work_order_code, service_request_id, technician_id, scheduled_start/end, status, completed_at |
| `inspection-results` | lab:read | part_number, characteristic, nominal, límites, measured, gage_id, gage_status, result, measured_at, superseded |
| `msa-studies` | msa:read | study_code, method, status, characteristic, part_number, gage_id, final_decision |
| `oot-cases` | oot:read | case_code, gage_id, calibration_id, detected_on, status, restriction_applied, impact_start/end, closed_at |

Las escrituras usan los endpoints de dominio existentes (p. ej. `POST /gages`, `POST /lab/requests`, `POST /lab/work-orders/{id}/results`, `POST /msa/studies/{id}/observations`), con las mismas validaciones y con idempotencia.

## 2. Eventos y webhooks

- **Outbox transaccional** (`outbox_events`): el evento se escribe en la misma transacción que el cambio de negocio. Una clave única de deduplicación por hecho evita duplicados, por ejemplo `gage.overdue:<gage>:<fecha de vencimiento>`.
- **Eventos**: `gage.created`, `gage.overdue` (barrido periódico), `calibration.released`, `certificate.uploaded`, `lab.request_created`, `lab.work_order_completed`, `msa.study_completed` (al aprobar el estudio), `oot.case_created`.
- **Entrega**:
  - Una entrega por (endpoint, evento).
  - Se firma con `X-GageTracker-Signature: sha256=HMAC_SHA256(secreto, "<timestamp>.<cuerpo>")` y lleva las cabeceras `X-GageTracker-Event`, `X-GageTracker-Delivery` (id estable: el receptor descarta duplicados) y `X-GageTracker-Timestamp`.
  - Reintentos tras 1 min, 5 min, 30 min, 2 h y 12 h. Al sexto intento fallido queda en `DEAD`; se puede reintentar manualmente.
  - Cada intento queda registrado (`webhook_attempts`).
- **URLs**: en producción solo https y sin direcciones privadas o loopback literales. Pendiente: resolución DNS anti-SSRF y cifrado del secreto en reposo.
- **Scheduler**: hilo en el proceso API, configurable con `SCHEDULER_ENABLED` y `SCHEDULER_INTERVAL_SECONDS`. Ejecuta fan-out, entrega, escalamientos de workflow y barrido de vencidos. Todos los trabajos son idempotentes. Para producción se recomienda un proceso *worker* dedicado.

## 3. Importaciones (CSV/Excel)

Flujo:
1. Carga del archivo, que se conserva bloqueado como documento.
2. Mapeo automático por nombre o alias, editable.
3. Validación con los **servicios de dominio** dentro de un *savepoint* que siempre se revierte.
4. Vista previa y errores por fila; detección de duplicados en el archivo y contra la base.
5. Confirmación: revalida y aplica todo o nada.
6. Historial y reproceso del mismo archivo con otro mapeo.

Importadores actuales: `gages` (inventario) y `msa_observations` (datos de un estudio). Las plantillas se descargan en `GET /integrations/importers/{code}/template`.

## 4. Conectores de dispositivos y Edge Connector

```
Instrumento ──(trama)──► Edge Connector (red local) ──HTTPS + X-API-Key──► /api/v1/connectors/readings
                         cola SQLite store-and-forward                   el servidor re-interpreta la trama
                                                                         con el mismo adaptador y guarda
                                                                         lectura + estado del instrumento
```

- **Adaptadores**: `generic_ascii` (una lectura por línea, `valor [unidad]`, punto o coma decimal) y `simulator`, para pruebas sin hardware. Ambos están probados.
- **Sin compatibilidad declarada con ningún fabricante.** Los protocolos de Mitutoyo, Sylvac, CMM, comparadores ópticos y equipos de torque son trabajo planeado, sin adaptador.
- **Lecturas**: tabla de solo inserción (`device_readings`). Son idempotentes por `reading_uid` y registran el estado del instrumento en el momento de la lectura. Una lectura con el instrumento fuera de servicio o vencido se guarda para trazabilidad, con advertencia. El análisis OOT las incluye como registros potencialmente afectados.
- **Agente de referencia**: `edge/edge_agent.py`.
  - Fuentes: simulador y líneas desde archivo o stdin.
  - Cola SQLite local: si no hay red no se pierde nada, y el reenvío no duplica.
  - Probado contra la API real en `backend/tests/test_edge_agent.py`.
  - Para despliegues privados: el agente solo necesita salida HTTPS hacia el servidor (no requiere puertos entrantes) y una llave del rol `edge_agent`.
