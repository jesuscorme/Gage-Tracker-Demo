# Reporte de avance 03 — Tercer bloque (MSA, motor estadístico, OOT, integraciones, configuración, compliance)

Fecha: 2026-10-30 · Commit base: `87666f0` · Esquema: revisión `0010_integrations`

## 1. Porcentaje acumulado estimado

**≈ 72 %** (objetivo del bloque: 80 %). El cálculo usa los pesos de `IMPLEMENTATION_ROADMAP.md`:

| Fases | Aporte |
|---|---|
| 0–5 (bloques anteriores) | 43.6 |
| MSA (85 % de 12) | 10.2 |
| OOT (85 % de 8) | 6.8 |
| Integraciones (70 % de 8) | 5.6 |
| Configuración y compliance (75 % de 8) | 6.0 |

Lo que falta para el 80 %:
- Adaptadores reales de fabricantes e integraciones ERP.
- Correo y un *worker* dedicado.
- Reporte MSA en español y plan MSA por característica.
- Expediente de auditoría en PDF y editor visual de workflows.
- Pendientes de seguridad: OIDC, límite de solicitudes, cifrado de secretos de webhook y protección anti-SSRF con resolución DNS.

## 2. Estado de cada fase

Ver la tabla completa en `MASTER_IMPLEMENTATION_PLAN.md` → «Estado de implementación».

| Fase | Estado |
|---|---|
| 0–5 | Completas, con los pendientes ya listados |
| 6 MSA | Funcional y validada |
| 7 OOT | Funcional |
| 8 Integraciones | Parcial (falta el ecosistema de fabricantes y ERP) |
| 9 Configuración y compliance | Funcional, con pendientes de experiencia de uso |
| 10–12 | Pendientes (siguiente bloque) |

## 3. Metodologías MSA implementadas

1. GRR cruzado, Promedio y Rango
2. GRR cruzado, ANOVA (con o sin interacción)
3. GRR anidado, ANOVA
4. Concordancia por atributos
5. Sesgo
6. Linealidad
7. Estabilidad (I-MR / X̄-R, 8 criterios configurables)
8. Tipo 1 (Cg/Cgk)

Las nueve metodologías del encargo quedan cubiertas: «Gage R&R cruzado», «ANOVA» y «Promedio y Rango» se realizan con los métodos 1 y 2. Cada método tiene su propio módulo, su validación de diseño y su versión de algoritmo (1.0.0).

## 4. Metodologías validadas

Todas tienen el estado VALIDADO en el motor. Evidencia por método en `docs/msa/`:
- Con **ejemplo publicado reproducido**: Promedio y Rango, ANOVA (tabla de sumas de cuadrados), Sesgo y Linealidad, con los ejemplos AIAG MSA 4ª ed.; Atributos, con el ejemplo de Fleiss.
- Con **implementación independiente**: ANOVA y anidado (statsmodels), atributos (statsmodels), sesgo y linealidad (scipy).
- Con **cálculo a mano**, sin ejemplo publicado disponible: Anidado, Estabilidad y Tipo 1.

**Sin validar**: los números de página del manual AIAG MSA, que no está disponible en el equipo. Los datos AIAG se transcribieron y se verificaron reproduciendo todos los valores intermedios publicados.

## 5. Resultados de pruebas estadísticas

Son 48 casos en `test_engine_grr.py` (34) y `test_engine_other.py` (14), todos aprobados. Resultados clave:
- **Promedio y Rango (datos AIAG):** EV 0.201857 / AV 0.229667 / GRR 0.305766 / PV 1.104596 / TV 1.146135 / %GRR 26.68 / ndc 5. Coincide con lo publicado (diferencia < 1e-4 por el redondeo del manual).
- **ANOVA:** las sumas de cuadrados coinciden con las publicadas: 3.1673 / 88.3619 / 0.3590 / 2.7589 / 94.6471. También coinciden con statsmodels en 12 diseños aleatorios (componentes con diferencia < 1e-12).
- **Sesgo:** 0.006667; s 0.212020; IC 95 % [−0.110746, 0.124079].
- **Linealidad:** pendiente −0.131667; intercepto 0.736667; R² 0.714.
- **Fleiss:** κ 0.209931 (publicado 0.210).
- **Límites y reproducibilidad:**
  - Se prueban datos incompletos, duplicados, inválidos y diseños fuera de las constantes tabuladas.
  - Sin variación, el resultado no inventa números ni produce NaN.
  - El resultado no depende del orden de entrada.
  - La huella de los datos es estable.

## 6. Funcionalidades OOT

- **Detección:** el caso se crea automáticamente al liberar una calibración con As Found fuera de tolerancia (configurable) o se registra a mano. Guarda los puntos As Found y As Left y la desviación máxima.
- **Restricción configurable:**
  - El instrumento queda fuera de servicio y se conserva su estado previo.
  - Una recalibración no levanta la retención.
  - La liberación ordinaria queda bloqueada (`oot_restriction`).
  - Solo se libera con `oot:approve` + `gages:release` y una calibración aceptable posterior a la detección.
- **Análisis retrospectivo:**
  - Toma desde la última calibración aceptable hasta la fecha de detección.
  - Identifica mediciones dimensionales (con cliente y estado del instrumento en ese momento), OT, asignaciones, estudios MSA y lecturas de dispositivos.
  - Admite registros manuales para producto o lote, con la limitación documentada.
  - Cada registro se evalúa (sin impacto / impacto / reinspección).
- **Investigación:** riesgo, alcance, reinspección, contención, disposición, acciones correctivas y notificación al cliente.
- **Workflow:** Detección → Restricción → Investigación → Evaluación de impacto → Acciones → Revisión → Aprobación → Cierre.
  - Hay segregación de funciones.
  - El cierre exige los registros configurados.
  - La cancelación de un caso abierto por error restaura el instrumento.

## 7. Integraciones disponibles

- API versionada con clientes por llave: cuentas de servicio con rol, plantas y caducidad, revocables y con registro de actividad.
- Idempotencia (`Idempotency-Key`).
- Contratos de intercambio v1 para 7 recursos.
- Outbox de 8 tipos de evento.
- Webhooks firmados con reintentos, *dead letter* y reintento manual.
- Importaciones (inventario y datos MSA) con mapeo, vista previa, errores por fila, historial y reproceso.
- Conectores: adaptador genérico ASCII y simulador. **Ninguna compatibilidad de fabricante está declarada.**
- Agente Edge Connector de referencia con cola local.

Documentación: `docs/integrations/README.md`.

## 8. Endpoints y contratos API

Hay **199 operaciones** bajo `/api/v1`, frente a 109 en el bloque 2: este bloque agrega 90. Por módulo:

| Módulo | Rutas |
|---|---|
| MSA | `/msa/methods`, `/msa/studies` (CRUD, `sequence`, `observations`, `validation`, `calculate`, `runs`, `conclusion`, `reports`, `workflow`), `/msa/observations/{id}/correct`, `/msa/runs/{id}` (+`verify`), `/msa/criteria` (+`templates`, `approve`, `retire`) |
| OOT | `/oot/settings`, `/oot/cases` (+`analysis`, `items`, `actions`, `release-gage`, `calibration-history`), `/oot/items/{id}/assess`, `/oot/actions/{id}/finish` |
| Configuración | `/config/catalogue`, `/config/items` (+`versions`, `retire`), `/config/versions/{id}/approve\|reject`, `/custom-fields/...`, `/forms/{entity}`, `/workflows/{entity}/definition`, `/workflows/{entity}/{id}` (+`transitions`), `/workflows/escalations/run` |
| Integraciones | `/integrations/api-clients`, `/integrations/webhooks`, `/integrations/webhook-deliveries`, `/integrations/events`, `/integrations/importers`, `/integrations/imports`, `/integrations/adapters`, `/integrations/devices`, `/connectors/readings`, `/exchange/{recurso}` |
| Compliance | `/compliance/matrix`, `processes/{code}`, `clauses`, `gages/{id}/dossier`, `certificates`, `approvals`, `pending`, `export.xlsx` |

## 9. Workflows configurables

Hay dos entidades con workflow configurable: estudio MSA y caso OOT. Una definición incluye:
- estados con capacidades;
- transiciones con permiso, acción (para la matriz de aprobación), autorización personal, comentario obligatorio, quórum de aprobaciones y segregación (responsable, creador o actor previo);
- escalamientos con notificación.

Cada definición se valida antes de guardarse: estados del sistema, alcanzabilidad, permisos y capacidades. Los cambios requieren un segundo aprobador y cada registro conserva su versión de workflow. Las matrices de aprobación (calibración, MSA, OOT) y las reglas declarativas se evalúan sobre hechos de la entidad.

## 10. Entidades y tablas nuevas (23; total 62)

| Módulo | Tablas |
|---|---|
| Configuración | `config_items`, `config_versions`, `custom_field_values`, `workflow_events` |
| Eventos | `outbox_events` |
| MSA | `msa_studies`, `msa_observations`, `msa_runs`, `msa_criteria_sets`, `msa_reports` |
| OOT | `oot_settings`, `oot_cases`, `oot_impact_items`, `oot_actions` |
| Integraciones | `api_clients`, `api_request_log`, `idempotency_records`, `webhook_endpoints`, `webhook_deliveries`, `webhook_attempts`, `import_jobs`, `devices`, `device_readings` |

Protecciones en base de datos (triggers):
- **Solo inserción:** `workflow_events`, `outbox_events`, `msa_runs`, `msa_reports`, `device_readings`, `webhook_attempts`, `api_request_log`.
- **Correcciones solo por reemplazo:** `msa_observations`.
- **Contenido inmutable:** `config_versions` y `msa_criteria_sets` (funciones nuevas `protect_config_version` y `protect_criteria_set`).

## 11. Migraciones

`0007_configuration`, `0008_msa`, `0009_oot`, `0010_integrations`. Incluyen permisos congelados (+15, total 48) y el rol nuevo `edge_agent`.

- La suite reconstruye el esquema (upgrade → downgrade → upgrade) en cada ejecución.
- `alembic check` no detecta diferencias.
- Las bases de desarrollo y E2E se migraron. Antes se respaldó la de desarrollo: `scratchpad/gagetracker-before-0010.dump`.

## 12. Pantallas

| Ruta | Contenido |
|---|---|
| `/msa` | Lista y alta con diseño por método y campos personalizados |
| `/msa/[id]` | Resumen y diseño, workflow y conclusión; datos (captura, pegado desde Excel, importación, corrección y anulación, secuencia, validación); resultados (indicadores, componentes, ANOVA, 2–4 gráficas por método, evaluación contra criterios, verificación de reproducibilidad, historial de cálculos); reportes PDF |
| `/msa/criteria` | Criterios: plantillas, reglas, aprobación y retiro |
| `/oot` | Lista y alta de casos |
| `/oot/[id]` | Caso, investigación, restricción y liberación, pendientes de cierre, workflow; análisis retrospectivo; acciones; historial de calibración |
| `/integrations` | Importaciones con mapeo, API, webhooks y entregas, dispositivos y simulador, eventos |
| `/settings/configuration` | Campos, formularios, workflows, matrices, reglas, ajustes OOT, pendientes de aprobación, versiones |
| `/compliance` | Matriz, cláusulas, pendientes, aprobaciones, certificados, expediente por instrumento, exportación |
| Instrumento (detalle) | Pestaña MSA / OOT y tarjeta de campos personalizados; el alta de instrumentos acepta campos personalizados |

## 13. Pruebas ejecutadas

| Suite | Resultado |
|---|---|
| Backend (PostgreSQL real) | **196/196** (118 previas + 78 nuevas: 48 motor, 8 MSA, 5 OOT, 6 configuración, 8 integraciones, 2 compliance, 1 agente edge) |
| Frontend Vitest | **11/11** |
| `tsc` y `next build` | OK |
| E2E en navegador (Edge, base `gagetracker_e2e`) | Bloque 3 **13/13**, regresión bloque 1 **13/13**, bloque 2 **9/9**, sin errores de JavaScript |

## 14. Defectos encontrados y corregidos

1. Las correcciones MSA insertaban la fila y luego la actualizaban. El trigger de inmutabilidad lo bloqueó y ahora la fila de reemplazo nace completa.
2. Las acciones OOT no se podían completar después de la aprobación, aunque el cierre lo exige. Se habilitó la capacidad «act» en revisión y aprobación.
3. El alta con campos personalizados inválidos dejaba la fila pendiente en la sesión. Ahora los campos se validan antes de crear (instrumento, estudio y caso).
4. `emit` detectaba duplicados con `rowcount`, que no es fiable con ON CONFLICT. Ahora usa `RETURNING`.
5. La consulta de certificados de patrones tenía un JOIN ambiguo; se hizo explícito.
6. Validación independiente del ANOVA anidado: las sumas de cuadrados tipo I de statsmodels no son válidas con un diseño singular. Se cambió a comparación de modelos y se documentó.
7. Defectos en las pruebas: expectativa errónea en el E2E (ANOVA da ndc 4 → NO ACEPTABLE, no CONDITIONAL), selectores de `<select>` envueltos por su etiqueta, URL del audit trail y orden de paginación con marcas de tiempo iguales.

## 15. Limitaciones

- Producto y lote no existen en el sistema; en OOT se registran a mano.
- No hay adaptadores de fabricantes.
- El scheduler corre dentro del proceso API.
- El PDF MSA está en inglés.
- El workflow se edita como JSON validado.
- El formulario configurado define secciones, pero aún no reordena las pantallas.
- El expediente de auditoría se exporta en XLSX, no en PDF.
- Las páginas citadas del manual AIAG MSA no están verificadas.
- Docker sigue sin probar.

## 16. Riesgos técnicos

- El secreto de webhook se guarda en claro: falta cifrado en reposo.
- La protección anti-SSRF es solo literal, sin resolución DNS.
- No hay límite de solicitudes.
- Con varios procesos API el scheduler se duplica; los trabajos son idempotentes, pero gastan recursos.
- El middleware de idempotencia hace operaciones de base de datos síncronas en un hilo aparte.
- El cálculo MSA es síncrono; con estudios grandes conviene una cola.
- Hay una dependencia nueva de numpy/scipy (fijadas).

## 17. Pendientes para producción

- OIDC/SSO.
- Límite de solicitudes por usuario y por llave.
- *Worker* dedicado y correo.
- Cifrado de secretos y almacenamiento S3.
- Prueba y endurecimiento de Docker.
- Respaldos y monitoreo.
- Validación del motor con casos del cliente (IQ/OQ si aplica).
- Reportes en español.
- Dashboard ejecutivo y experiencia de usuario (siguiente bloque).

---

*Aviso: Gage Tracker facilita el control y la demostración de evidencia; no certifica organizaciones ni garantiza cumplimiento normativo.*
