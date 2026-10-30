# Roadmap de implementación

Avance medido por funcionalidad probada y utilizable, no por volumen de código.

## Avance global estimado: **≈ 18 %**

| Fase | Peso aprox. | Estado | Avance |
|---|---|---|---|
| 0 · Descubrimiento | 2 % | Completa | 100 % |
| 1 · Fundaciones | 10 % | Completa con pendientes no bloqueantes | ≈ 90 % |
| 2 · Gage Management | 8 % | Primera versión funcional | ≈ 65 % |
| 3–12 | 80 % | No iniciadas | 0 % |

## Siguiente incremento recomendado (próximo ~20 %)

1. **Cerrar Fase 2**
   - Documentos/adjuntos del instrumento (almacenamiento S3-compatible + metadatos, `attachments`).
   - Exportación básica (CSV/Excel) del listado filtrado.
   - Asignaciones/préstamos (`gage_assignments`) si el negocio lo requiere.
   - Regla de unicidad configurable (organización / planta).
   - Concurrencia optimista (`version`) en edición.
   - Revisión de cierre de fase (plan §8.3) con tabla PASS/FAIL.
2. **Endurecimiento de Fase 1**
   - Rate limiting de login, política de bloqueo por intentos.
   - Validar `docker compose up` en un equipo con Docker.
   - Decidir OIDC (ADR-004) y almacenamiento de sesión (cookie httpOnly).
3. **Iniciar Fase 3 · Calibration Management**
   - Actividades diferenciadas (calibración externa / interna / verificación).
   - As Found / As Left, certificado, revisión y liberación, que reemplazan la fecha manual provisional.

## Orden de fases (sin cambios respecto al plan)

M0 → M1 → M2 → M3 Calibration → M4 Standards/Competency → M5 Laboratory → M6 MSA → M7 OOT → M8 Integrations → M9 Configuration/Compliance → M10 Dashboard → M11–12 Release.
