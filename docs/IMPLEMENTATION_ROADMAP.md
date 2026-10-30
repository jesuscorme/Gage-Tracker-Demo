# Roadmap de implementación

Avance medido por funcionalidad probada y utilizable, no por volumen de código.

## Avance global estimado: **≈ 84 %** del alcance total (bloque 4, 2026-10-30)

Medido por funcionalidad probada. Ver la matriz del plan maestro y `PROGRESS_REPORT_04.md` §2.

| Fase | Peso | Estado | Avance |
|---|---|---|---|
| 0 · Descubrimiento | 2 % | Completa | 100 % |
| 1 · Fundaciones | 10 % | Completa salvo OIDC, MFA y RLS | 92 % |
| 2 · Gage Management | 8 % | Completa salvo unicidad configurable | 95 % |
| 3 · Calibration | 12 % | Completa salvo correo | 87 % |
| 4 · Standards + Competency | 8 % | Funcional | 85 % |
| 5 · Laboratory | 10 % | Funcional + reportes de tiempos y capacidad | 82 % |
| 6 · MSA | 12 % | 8 métodos validados, PDF ES/EN, regresión *golden* | 90 % |
| 7 · OOT | 8 % | Completa salvo plantilla de notificación | 87 % |
| 8 · Integrations | 8 % | Sin adaptadores de fabricante ni ERP | 70 % |
| 9 · Configuration & Compliance | 8 % | Sin editor visual ni expediente PDF | 78 % |
| 10 · Dashboard / reportes | 5 % | Tablero ejecutivo + 22 reportes | 95 % |
| 11–12 · Producción y liberación | 9 % | Seguridad, respaldo probado, rendimiento, docs, demo, UAT preparado; Docker y CI sin ejecutar; UAT pendiente | 55 % |

## Pendientes para la liberación productiva

1. Ejecutar el despliegue con Docker (`DEPLOYMENT_PRIVATE.md` §6) y el pipeline de CI.
2. UAT con usuarios (`UAT.md`).
3. Revisión de seguridad externa; MFA/OIDC; límite por IP; anti-SSRF con DNS.
4. Almacenamiento de objetos (S3/Blob), SMTP, adaptadores de fabricantes y ERP según prioridad comercial.
