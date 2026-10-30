# Roadmap de implementación

Avance medido por funcionalidad probada y utilizable, no por volumen de código.

## Avance global estimado: **≈ 45 %** (bloque 2, 2026-10-29)

| Fase | Peso | Estado | Avance |
|---|---|---|---|
| 0 · Descubrimiento | 2 % | Completa | 100 % |
| 1 · Fundaciones | 10 % | Completa con pendientes no bloqueantes | 90 % |
| 2 · Gage Management | 8 % | Completa salvo unicidad configurable | 95 % |
| 3 · Calibration Management | 12 % | Flujo integral funcional | 85 % |
| 4 · Standards + Competency | 8 % | Funcional | 85 % |
| 5 · Laboratory Operations | 10 % | Funcional | 80 % |
| 6 · MSA | 12 % | No iniciada | 0 % |
| 7 · OOT & Impact | 8 % | No iniciada (marca As Found OOT disponible) | 0 % |
| 8 · Integrations | 8 % | No iniciada (import/export CSV/XLSX de inventario ya existe) | 0 % |
| 9 · Configuration & Compliance | 8 % | No iniciada | 0 % |
| 10 · Dashboard/reportes | 5 % | Parcial implícito (tableros por módulo) | 0 % |
| 11–12 · Producción y liberación | 9 % | No iniciadas | 0 % |

## Para cerrar las Fases 2–5 (antes o en paralelo al siguiente bloque)

1. Correo para notificaciones y tareas programadas de alertas (vencimientos).
2. Cotización y QR/código de barras en laboratorio; capacidad por recurso.
3. Unicidad de Gage ID configurable; préstamos de instrumentos.
4. Endurecimiento de Fase 1: OIDC, rate limiting, cookie httpOnly; almacenamiento S3.
5. Guía de arranque (onboarding) para otorgar autorizaciones iniciales.

## Siguiente bloque (planificado por el propietario)

**MSA Management + motor estadístico + OOT & Impact Analysis** (Fases 6 y 7):
- Motor estadístico separado, versionado y validado con casos de referencia; primera metodología completa (Gage R&R cruzado ANOVA / Average & Range).
- OOT: aprovechar `as_found_in_tolerance = false` de calibraciones liberadas y el estado del equipo guardado en cada medición dimensional para identificar la ventana de impacto.
