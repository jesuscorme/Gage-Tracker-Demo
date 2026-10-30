# UAT — Validación con usuarios

**Estado global: PENDIENTE.** Ningún escenario se marca como aprobado hasta que lo ejecute y firme el usuario responsable. La columna «Evidencia técnica» indica la prueba automatizada que ya cubre el flujo; **no sustituye** la validación del usuario.

Entorno sugerido: la instancia demo (`scripts/demo-reset.ps1`, organización «[DEMO] Autopartes Demostración S.A.», usuarios `@demo.example.com`) o un entorno de staging con datos del cliente.

## Escenarios

| # | Perfil | Objetivo | Precondiciones | Pasos | Resultado esperado | Resultado obtenido | Evidencia técnica | Estado |
|---|---|---|---|---|---|---|---|---|
| 1 | Administrador de plataforma | Instalar y verificar la plataforma | Servidor con Docker, `deploy/.env` completo | `DEPLOYMENT_PRIVATE.md` §2 y lista de verificación §6 | Servicios sanos; `/health/ready` en 0011; TLS válido | | Ninguna (Docker no probado) | PENDIENTE |
| 2 | Administrador de plataforma | Respaldar y restaurar | Instalación del escenario 1 con datos | `backup.sh` → servidor nuevo → `restore.sh` | Conteos y documentos idénticos | | `BACKUP_RESTORE.md` (Windows, probado) | PENDIENTE |
| 3 | Administrador de organización | Arrancar la organización | Cuenta org_admin | Plantas, usuarios por rol, autorizaciones, tipos, patrones, servicios, criterios MSA (aprobados por otra persona) | Todo registrado y auditado; los criterios quedan aprobados por un segundo usuario | | E2E 1–3, `test_rbac`, `test_msa` | PENDIENTE |
| 4 | Administrador de organización | Gestionar cuentas | Usuario técnico activo | Generar enlace de restablecimiento; el usuario fija contraseña; verificar bloqueo tras 5 fallos | El enlace sirve una sola vez y cierra la sesión anterior; 429 tras 5 fallos | | E2E 4, `test_security` | PENDIENTE |
| 5 | Responsable de metrología | Controlar el inventario y los vencimientos | Instrumentos cargados | Tablero con filtros; reporte de calibraciones vencidas en PDF y Excel; programa de calibración | Cifras del tablero = reporte = listados | | `test_dashboard`, `test_reports`, E2E 4 | PENDIENTE |
| 6 | Responsable de metrología | Gestionar un caso OOT | Calibración con As Found fuera de tolerancia liberada | Revisar el caso, generar el análisis, evaluar los registros, acciones, aprobar, liberar el instrumento, cerrar | Instrumento bloqueado hasta la liberación autorizada; cierre solo con los registros exigidos | | `test_oot`, E2E 3 | PENDIENTE |
| 7 | Técnico de calibración | Calibrar un instrumento | Autorización INTERNAL_CALIBRATION; patrón vigente | Iniciar, capturar As Found / As Left, patrón, enviar a revisión | Resultado calculado; no puede revisar su propia actividad | | `test_calibration`, E2E 2 | PENDIENTE |
| 8 | Técnico de laboratorio | Atender una orden | OT programada con instrumento disponible | Iniciar, capturar mediciones, corregir una lectura, completar | Corrección con historial; sin mediciones con instrumentos no disponibles | | `test_laboratory`, E2E 2 | PENDIENTE |
| 9 | Evaluador MSA | Ejecutar un estudio GRR | Autorización MSA_EVALUATION; criterios aprobados | Crear estudio, pegar datos, validar, calcular, enviar; otro usuario concluye y aprueba; emitir PDF | Resultados iguales a la referencia AIAG; decisión según criterios; PDF con versión del algoritmo | | `test_engine_*`, `test_msa`, E2E 3 | PENDIENTE |
| 10 | Evaluador MSA | Comprobar la reproducibilidad | Estudio calculado | «Verificar reproducibilidad» | Resultados idénticos con el motor actual | | `test_msa`, E2E 3 | PENDIENTE |
| 11 | Auditor | Preparar una auditoría | Rol auditor | Matriz de evidencias, cláusulas, expediente de un instrumento, aprobaciones, exportación Excel | Solo lectura; aviso de que el sistema no certifica; exportación auditada | | `test_compliance`, E2E 3 | PENDIENTE |
| 12 | Auditor | Revisar la trazabilidad | Rol auditor | Bitácora de auditoría de un instrumento y descargas de documentos | Cada cambio con usuario, fecha, valores anteriores y nuevos | | `test_platform`, `test_security` | PENDIENTE |
| 13 | Usuario solicitante | Pedir un servicio al laboratorio | Rol requester | Crear solicitud; seguir su estado; consultar el informe emitido | Solo ve sus solicitudes | | `test_laboratory` | PENDIENTE |
| 14 | Cualquier usuario | Usar la plataforma en tableta o móvil | Dispositivo de 390–1024 px | Tablero, instrumentos, solicitudes, órdenes, certificados | Uso posible sin desplazamiento horizontal de la página | | E2E 4 (390 px) | PENDIENTE |
| 15 | Cualquier usuario | Trabajar en inglés | — | Cambiar a EN; navegar; emitir un reporte | Interfaz y reportes en inglés; datos históricos sin cambios | | E2E 1 y 4 | PENDIENTE |

## Firma

| Escenarios | Responsable | Fecha | Resultado | Firma |
|---|---|---|---|---|
| | | | | |
