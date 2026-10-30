# Roadmap de implementación

Avance medido por funcionalidad probada y utilizable, no por volumen de código.

## Avance global estimado: **≈ 72 %** (bloque 3, 2026-10-30)

| Fase | Peso | Estado | Avance |
|---|---|---|---|
| 0 · Descubrimiento | 2 % | Completa | 100 % |
| 1 · Fundaciones | 10 % | Completa con pendientes no bloqueantes | 90 % |
| 2 · Gage Management | 8 % | Completa salvo unicidad configurable | 95 % |
| 3 · Calibration Management | 12 % | Flujo integral + eventos + matriz de aprobación | 86 % |
| 4 · Standards + Competency | 8 % | Funcional | 85 % |
| 5 · Laboratory Operations | 10 % | Funcional | 80 % |
| 6 · MSA | 12 % | 8 métodos validados, criterios, versionado, reportes | 85 % |
| 7 · OOT & Impact | 8 % | Detección, restricción, análisis, acciones, cierre | 85 % |
| 8 · Integrations | 8 % | API/llaves, idempotencia, webhooks, importaciones, conectores (sin fabricantes) | 70 % |
| 9 · Configuration & Compliance | 8 % | Campos, formularios, workflows, matrices, reglas, compliance | 75 % |
| 10 · Dashboard/reportes | 5 % | Parcial implícito (tableros por módulo) | 0 % |
| 11–12 · Producción y liberación | 9 % | No iniciadas | 0 % |

## Pendientes para cerrar las Fases 2–9

1. Correo (notificaciones y escalamientos); worker dedicado para el scheduler.
2. Adaptadores de fabricantes probados en sitio; integraciones ERP.
3. Reporte MSA en español; plan MSA por característica; método de detección de señales (atributos).
4. Expediente de auditoría en PDF; formularios configurados aplicados al diseño de pantallas; editor visual de workflows.
5. Seguridad: OIDC, rate limiting por usuario y cliente API, cifrado de secretos de webhook, anti-SSRF con resolución DNS, almacenamiento S3.

## Siguiente bloque (planificado por el propietario)

Dashboard ejecutivo, experiencia de usuario, pruebas integrales, despliegue híbrido y liberación comercial.
