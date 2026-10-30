# Reporte técnico 02 — segundo bloque (Gage, Calibration, Standards, Competency, Laboratory)

**Fecha:** 2026-10-29 · **Versión API:** 0.5.0 · **Revisión de esquema:** `0006_laboratory`

## 1. Porcentaje estimado acumulado: **≈ 45 %**

Medido por funcionalidad probada y utilizable, con pesos por fase (ver `IMPLEMENTATION_ROADMAP.md`):

| Fase | Peso | Avance | Aporte |
|---|---|---|---|
| 0 · Descubrimiento | 2 % | 100 % | 2.0 |
| 1 · Fundaciones | 10 % | 90 % | 9.0 |
| 2 · Gage Management | 8 % | 95 % | 7.6 |
| 3 · Calibration Management | 12 % | 85 % | 10.2 |
| 4 · Standards + Competency | 8 % | 85 % | 6.8 |
| 5 · Laboratory Operations | 10 % | 80 % | 8.0 |
| 6–12 | 50 % | 0 % | 0 |
| **Total** | | | **≈ 43.6 → 45 %** |

El objetivo era 50 %. La diferencia se explica por pendientes documentados en §4, sobre todo: notificaciones por correo, cotización de solicitudes, código QR/barras, roles personalizados y endurecimiento de Fase 1 (OIDC, rate limiting). No se simularon para inflar el porcentaje.

## 2. Avance por fase

| Fase | Estado | Resumen |
|---|---|---|
| 0 | COMPLETADO | Línea base, ADRs, roadmap |
| 1 | COMPLETADO (pendientes no bloqueantes) | Plataforma multi-tenant, RBAC (35 permisos, 7 roles), auditoría inmutable |
| 2 | COMPLETADO salvo unicidad configurable | Expediente completo, transferencias, documentos/fotos, importación/exportación |
| 3 | PARCIAL avanzado | Flujo integral con As Found/As Left, certificados, revisión/aprobación/liberación, calendario |
| 4 | PARCIAL avanzado | Patrones con certificados y vigencia; perfiles, matriz, autorizaciones verificadas |
| 5 | PARCIAL avanzado | Solicitudes, OT, programación con validaciones, captura dimensional, informes PDF, KPIs |

## 3. Funcionalidades completadas (probadas)

**Gage Management**
- Expediente con fecha de adquisición y de puesta en servicio, última verificación, fotografías y documentos.
- **Transferencia/reasignación** (planta, departamento, ubicación, responsable) con motivo e historial de movimientos (`gage_movements`, append-only); la edición ordinaria ya no cambia la asignación.
- La **fecha de última calibración solo se registra al alta/importación** (registro inicial); después la mueve exclusivamente la liberación de una calibración. Se eliminó la fecha manual provisional del bloque anterior.
- **Importación CSV/XLSX todo-o-nada** con validación previa (dry-run) y errores por fila; plantilla descargable.
- **Exportación** CSV/XLSX con los mismos filtros del listado.
- Expediente con pestañas: General · Calibraciones · Documentos · Historial (estado, movimientos, auditoría).

**Calibration Management**
- Tipos diferenciados: calibración externa, interna, verificación de rutina; habilitación y evidencias requeridas **configurables por organización y por planta**.
- Flujo: Planificada → Solicitada → Programada → En ejecución → Revisión técnica → Por aprobar → Aprobada → Liberada (devolución y cancelación con motivo).
- Calibration ID secuencial por organización (`CAL-2026-00001`).
- Registro: proveedor/acreditación, técnico, método, condiciones ambientales, incertidumbre, ajuste, resultado, observaciones, revisor, aprobador, fecha de liberación, vencimiento.
- **As Found y As Left como registros separados**; correcciones por sustitución (el valor original se conserva; trigger de BD lo impide modificar).
- Resultado calculado (Conforme / Conforme tras ajuste / No conforme) o declarado si no hay puntos.
- **Certificados PDF** con metadatos; reemplazo de un certificado aprobado solo con permiso de liberación y motivo, conservando el anterior (SUPERSEDED).
- **Liberación transaccional**: actualiza fecha y vencimiento del instrumento y su estado (no conforme ⇒ Out of Service); bloquea evidencias.
- Un instrumento retenido por una calibración no puede liberarse manualmente; cancelar restaura el estado previo.
- Calendario mensual, panel de vencidos/próximos/pendientes, instrumentos sin actividad planificada.
- Notificaciones en la app (revisión pendiente, aprobación pendiente, devolución, liberación) con preferencias por usuario.

**Standards Management**
- Catálogo con categorías (bloques patrón, referencia, pieza maestra, master de ajuste, instrumento de referencia, temperatura, presión, otro + subtipo).
- Certificados PDF inmutables con trazabilidad e incertidumbre; vigencia y estados (Vigente, Por vencer, Vencido, Sin certificado, Restringido, Inactivo).
- **Validación de uso**: un patrón no vigente solo se usa con excepción documentada por un usuario con `standards:exception`.
- Por cada uso se guarda **instantánea**: estado, certificado y vigencia en esa fecha; consulta "uso en actividades" por patrón.

**Competency Management**
- Perfiles (técnico, calibrador interno, verificador, evaluador MSA, revisor, aprobador…), puesto, planta.
- Catálogo de competencias con vigencia; registros de formación/evaluación/certificación (append-only) con evidencias.
- Matriz de competencias.
- **Autorizaciones** por actividad, con alcance opcional por tipo de instrumento y planta, vigencia, fundamento; revocación con motivo.
- Validación en: programación y ejecución de calibraciones internas/verificaciones, revisión técnica, aprobación, asignación y ejecución de OT, captura dimensional, emisión de informes.

**Laboratory Operations**
- Catálogo de servicios (horas estándar, autorización requerida, si exige captura dimensional).
- Solicitudes (SR) con prioridad, fechas solicitada/compromiso, documentos; el solicitante ve solo las suyas.
- OT a partir de solicitudes aprobadas; **programación con validación** de autorización del técnico, ausencias, traslapes del técnico, equipo disponible, que no venza antes del trabajo y que no esté reservado; reprogramación con motivo.
- Captura dimensional (múltiples características y muestras), con equipo asignado y **rechazo de mediciones con equipo no disponible**; correcciones por sustitución.
- **Informes** con instantánea congelada y **PDF** generado; reemisión como nueva revisión con motivo; revisor distinto del técnico.
- KPIs reales: solicitudes por revisar, OT abiertas/en ejecución/atrasadas/completadas, % a tiempo, tiempo de respuesta, carga por técnico y capacidad utilizada (horas/día y días laborables configurables).
- Tablero semanal de programación.

## 4. Funcionalidades parciales / pendientes

| Área | Pendiente |
|---|---|
| Gage | Regla de unicidad configurable por planta; préstamos/asignaciones temporales; vistas guardadas |
| Calibration | Envío de notificaciones por correo; alertas programadas (hoy se calculan al consultar); plantillas de puntos por tipo de instrumento |
| Standards | Uso de patrones en OT de laboratorio (hoy solo en calibraciones) |
| Competency | Edición de registros (por diseño son append-only; falta flujo de anulación con motivo) |
| Laboratory | Cotización; QR/código de barras; capacidad por recurso/equipo (hoy por técnico); vista Gantt con arrastre |
| Plataforma | OIDC, rate limiting de login, cookie httpOnly, RLS, roles personalizados, almacenamiento S3 (hoy disco local con interfaz preparada) |
| Fuera de alcance (siguiente bloque) | MSA, motor estadístico, OOT & Impact (hay marca *As Found fuera de tolerancia* como enlace futuro) |

## 5. Tablas nuevas y modificadas

**Nuevas (26):** `attachments`, `code_sequences`, `gage_movements`, `standards`, `standard_certificates`, `personnel_profiles`, `competencies`, `competency_records`, `authorizations`, `calibration_settings`, `calibration_activities`, `calibration_points`, `calibration_certificates`, `calibration_standard_usages`, `calibration_status_history`, `notifications`, `notification_preferences`, `lab_settings`, `lab_services`, `technician_absences`, `service_requests`, `work_orders`, `work_order_equipment`, `work_order_events`, `inspection_results`, `measurement_reports`.
**Modificadas:** `gages` (+`acquisition_date`, `in_service_date`, `last_verification_date`), `permissions`/`roles`/`role_permissions` (datos: +22 permisos, +2 roles).

Restricciones de integridad añadidas: CHECKs de estados/categorías/fechas/límites, unicidad por organización de códigos, FK con RESTRICT, triggers *append-only* (`gage_movements`, `competency_records`, `calibration_status_history`, `work_order_events`) y *solo sustitución* (`calibration_points`, `inspection_results`).

## 6. Migraciones

| Revisión | Contenido |
|---|---|
| `0003_gage_completion` | Documentos, secuencias, campos de fechas del instrumento, movimientos; permisos `gages:transfer`, `gages:import`; roles `lab_technician`, `requester` |
| `0004_standards_competency` | Patrones y certificados (FK circular resuelta con `create_foreign_key`), perfiles, competencias, registros, autorizaciones |
| `0005_calibration` | Configuración, actividades, puntos, certificados, uso de patrones, historial, notificaciones; función `protect_measurement_row()` |
| `0006_laboratory` | Servicios, capacidad, ausencias, solicitudes, OT, equipo, eventos, resultados, informes |

Verificadas desde base vacía y en reversa (upgrade → downgrade base → upgrade) en cada corrida de pruebas; `alembic check` sin diferencias.

## 7. Endpoints

109 operaciones (`/api/docs`). Nuevas por módulo:

- **Documentos:** `GET/POST /attachments`, `GET /attachments/{id}/download`, `POST /attachments/{id}/remove`
- **Gages:** `POST /gages/{id}/transfer`, `GET /gages/{id}/movements`, `POST /gages/import[?dry_run]`, `GET /gages/import/template`, `GET /gages/export`, `GET /gages/{id}/calibration-summary`
- **Standards:** `GET/POST /standards`, `GET/PATCH /standards/{id}`, `POST /standards/{id}/transitions`, `GET/POST /standards/{id}/certificates`, `GET /standards/{id}/usages`
- **Competency:** `GET /competency/people`, `PUT /competency/people/{user_id}`, `GET/POST /competency/competencies`, `PATCH /competency/competencies/{id}`, `GET/POST /competency/records`, `GET /competency/matrix`, `GET/POST /competency/authorizations`, `POST /competency/authorizations/{id}/revoke`, `GET /competency/authorized-users`
- **Calibration:** `GET/PUT /calibration-settings`, `GET /calibrations/overview`, `GET /calibrations/calendar`, `GET/POST /calibrations`, `GET/PATCH /calibrations/{id}`, `POST /calibrations/{id}/{request|schedule|start|points|standards|certificates|submit|review|approve|release|cancel}`, `POST /calibrations/{id}/standards/{usage}/remove`
- **Laboratory:** `GET /lab/dashboard`, `GET/PUT /lab/settings`, `GET/POST /lab/services`, `PATCH /lab/services/{id}`, `GET/POST /lab/absences`, `GET/POST /lab/requests`, `GET /lab/requests/{id}`, `POST /lab/requests/{id}/{decision|cancel}`, `GET/POST /lab/work-orders`, `GET /lab/work-orders/{id}`, `POST /lab/work-orders/{id}/{schedule|start|results|complete|cancel|reports}`, `GET /lab/reports`, `GET /lab/reports/{id}`
- **Notificaciones:** `GET /notifications`, `POST /notifications/read`, `GET/PUT /notifications/preferences`, `GET /alerts`

## 8. Pantallas

Nuevas: Importación de inventario · Expediente con pestañas + transferencia + documentos · Calibraciones (panel + listado) · Detalle de calibración (flujo completo) · Calendario · Patrones (listado/alta) · Detalle de patrón (certificados, uso, documentos) · Competencias (personal, matriz, autorizaciones, catálogo) · Tablero de laboratorio · Solicitudes (listado/alta/detalle) · Programación semanal · Órdenes de trabajo (listado/detalle con programación, captura dimensional, informes) · Informes (listado/detalle/PDF) · Configuración técnica (tipos de actividad y evidencias, servicios, capacidad, ausencias) · Campana de notificaciones y alertas. Todas con estados de carga, vacío, error y confirmación; español e inglés.

## 9. Flujos funcionales verificados en navegador

1. Alta de patrón → certificado PDF → vigente.
2. Alta de instrumento con fechas → transferencia con motivo → documento → historial.
3. Exportación XLSX; importación con errores bloqueada; importación válida.
4. Calibración interna: planificar → solicitar → programar (técnico autorizado) → ejecutar (condiciones, As Found, patrón) → revisión (otro usuario) → aprobación (otro usuario) → liberación ⇒ instrumento Calibrated y disponible.
5. Laboratorio: solicitud (solicitante) → aprobación con fecha compromiso → OT → programación con equipo → ejecución y medición (técnico autorizado) → cierre → informe emitido por revisor → solicitante ve informe y notificación.
6. Configuración técnica, competencias y autorizaciones visibles.

## 10. Pruebas ejecutadas (resultados reales)

| Suite | Resultado |
|---|---|
| Backend pytest, PostgreSQL 16 | **118 / 118 PASS** — plataforma 13, RBAC 18, aislamiento 9, reglas de estado 20, instrumentos 20, completitud de instrumentos 10, patrones/competencias 5, calibración 16, laboratorio 7 |
| Frontend Vitest | **6 / 6 PASS** |
| TypeScript `tsc --noEmit` | PASS |
| `next build` | PASS (29 rutas) |
| E2E navegador bloque 1 (regresión) | **13 / 13 PASS** |
| E2E navegador bloque 2 | **9 / 9 PASS**, sin errores de página |

Cobertura de los 15 puntos obligatorios: (1) alta/modificación, (2) unicidad Gage ID, (3) vencimientos, (4) restricción de vencidos (no asignables a OT, no medibles, no "liberables" manualmente), (5) As Found/As Left, (6) aprobación con segregación, (7) actualización del estado del instrumento, (8) patrones vigentes y excepción, (9) autorización de técnicos, (10) solicitudes, (11) programación y asignación, (12) captura dimensional, (13) informes, (14) aislamiento entre organizaciones (calibración, documentos, patrones, laboratorio), (15) matriz de permisos por los 7 roles.

**No ejecutado:** Docker (no instalado). Los scripts E2E de navegador viven fuera del repositorio. El E2E corrió sobre una base aparte (`gagetracker_e2e`) para no mezclar datos de prueba con la organización de desarrollo existente.

## 11. Errores encontrados y corregidos

1. Respuestas con relaciones obsoletas tras confirmar (transferencia) → `populate_existing` al leer instrumentos.
2. FK circular `standards ↔ standard_certificates` emitida en línea por Alembic → movida a `create_foreign_key` posterior.
3. Rango del calendario sin límite → máximo 120 días con error explícito.
4. Fechas "hoy" del frontend en UTC (de noche en México mostraba el día siguiente) → fecha local.
5. Campo de archivo con el mismo nombre accesible que el botón "Subir archivo" → etiqueta descriptiva.
6. Diálogo de transición enviaba la fecha manual de calibración eliminada → retirada.
7. Ajustes de pruebas existentes a las nuevas reglas (transferencia y fecha de calibración controladas).

## 12. Riesgos

- Almacenamiento local de archivos: válido en un solo servidor; para Cloud se requiere S3-compatible y respaldo conjunto BD + archivos.
- Notificaciones solo en la app; sin correo, los avisos dependen de que el usuario entre.
- Autenticación local sin OIDC ni rate limiting (heredado de Fase 1).
- Una organización recién creada no puede revisar ni aprobar hasta otorgar autorizaciones: es correcto, pero requiere guía de arranque (onboarding).
- Indicadores de capacidad simplificados (por técnico, sin calendario de turnos).

## 13. Archivos

Backend: `app/core/{storage,sequences}.py`; módulos nuevos `documents`, `standards`, `competency`, `calibration`, `laboratory`, `notifications`; `gages/{models,schemas,service,router,io}.py`; `identity/permissions.py`; migraciones `0003`–`0006`; pruebas `test_gage_completion`, `test_standards_competency`, `test_calibration`, `test_laboratory` y ajustes en las existentes.
Frontend: `lib/{api,types,types-modules,messages-modules,i18n,status,hooks}`; componentes `documents`, `gage-dialogs`, `notifications`, `ui` (tabs, KPIs, diálogos), `shell`, `icons`; páginas en `calibrations/`, `standards/`, `competency/`, `laboratory/`, `gages/import`, `settings/technical`.

## 14. Ejecutar y probar

Ver `README.md`. Resumen:

```powershell
powershell -File scripts/dev-db.ps1 start
cd backend; .venv\Scripts\python -m pip install -r requirements-dev.txt; .venv\Scripts\python -m alembic upgrade head
.venv\Scripts\python -m uvicorn app.main:app --port 8100
cd ..\frontend; npm ci; $env:API_URL="http://127.0.0.1:8100"; npx next build; npx next start -p 3200
# Pruebas
cd backend; .venv\Scripts\python -m pytest
cd frontend; npm test; npm run typecheck
```

Para probar el flujo completo, el administrador debe: crear tipo de instrumento → registrar usuarios con roles → **otorgar autorizaciones** (Competencias → Autorizaciones) → registrar un patrón con certificado → planificar una calibración.
