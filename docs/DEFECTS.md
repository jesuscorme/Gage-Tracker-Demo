# Registro de defectos y criterios de liberación

Clasificación: CRITICAL (pérdida o exposición de datos, cálculo incorrecto liberado, sistema inutilizable) · HIGH (control de seguridad o integridad roto, flujo crítico bloqueado) · MEDIUM (funcionalidad degradada con alternativa) · LOW (cosmético o de mantenimiento).

## Corregidos en el bloque 4

| Id | Sev. | Descripción | Corrección y evidencia |
|---|---|---|---|
| D4-01 | HIGH | En escritura (estudios MSA, criterios de planta, dispositivos) se aceptaba un `plant_id` de **otra organización** | Validación con `get_plant`; prueba `test_records_cannot_reference_another_organizations_plant` |
| D4-02 | HIGH | Dependencias con vulnerabilidades publicadas: Next.js (crítica); cryptography, starlette, python-multipart, fpdf2, postcss, sharp | Actualizadas; pip-audit y npm audit = 0; 234 pruebas y 43 E2E en verde |
| D4-03 | MEDIUM | El filtro de planta del tablero aceptaba la planta de otra organización (sin fuga de datos) | 404; `test_dashboard_respects_permissions_and_plant_scope` |
| D4-04 | MEDIUM | Regresión: una organización nueva perdió la orientación «Aún no hay instrumentos» al rediseñar el tablero (detectada por E2E) | Estado vacío con acción «+ Nuevo instrumento» restaurado |
| D4-05 | MEDIUM | El tablero tardaba 4.8 s tras una carga masiva o restauración por estadísticas desactualizadas | `ANALYZE` en la restauración; documentado; 114 ms medido |
| D4-06 | LOW | Gráficas: conteos mostrados como «4.000» y eje negativo con valores cero | Formato entero y eje desde cero |
| D4-07 | LOW | Textos fijos en inglés en la pantalla MSA y reporte MSA solo en inglés | i18n; reporte ES/EN |
| D4-08 | LOW | Imports y variables sin uso | ruff limpio |

Defectos de bloques anteriores: `PROGRESS_REPORT_02.md` (sección de errores corregidos) y `PROGRESS_REPORT_03.md` §14; todos corregidos.

## Abiertos

| Id | Sev. | Descripción | Tratamiento |
|---|---|---|---|
| O-01 | HIGH | Despliegue con Docker (instalación privada y nube) **no ejecutado** | Ejecutar `DEPLOYMENT_PRIVATE.md` §6 en un servidor con Docker. **Bloquea la liberación productiva** |
| O-02 | HIGH | Pipeline de CI escrito pero **nunca ejecutado** | Configurar el repositorio remoto y ejecutar. Bloquea la liberación productiva |
| O-03 | MEDIUM | Sin MFA ni SSO (OIDC) | Requisito previo a exponer la plataforma a Internet |
| O-04 | MEDIUM | El bloqueo por cuenta puede usarse para bloquear a un usuario conocido; no hay límite por IP | Límite por IP en el proxy o WAF |
| O-05 | MEDIUM | Anti-SSRF de webhooks solo literal (sin resolución DNS) | Validar la IP resuelta antes de cada envío |
| O-06 | MEDIUM | Almacenamiento de documentos solo en disco o volumen (sin S3/Blob) | Adaptador de almacenamiento de objetos para la nube |
| O-07 | MEDIUM | Páginas del manual AIAG MSA citadas sin verificar (manual no disponible) | Verificar contra la copia controlada |
| O-08 | MEDIUM | Sin prueba de penetración externa | Contratar antes de la liberación |
| O-09 | LOW | Sin correo: avisos y restablecimiento dependen de la aplicación y del administrador | SMTP configurable |
| O-10 | LOW | `postcss` forzado por `overrides` dentro de Next 15 | Eliminar al migrar a Next 16 |
| O-11 | LOW | Aviso de deprecación del cliente de pruebas (`httpx` → `httpx2`) | Actualizar la dependencia de pruebas |
| O-12 | LOW | ESLint (`next lint`) no configurado; la calidad del frontend depende de `tsc` | Configurar ESLint |
| O-13 | LOW | La descripción del modelo estadístico en el PDF MSA sale en inglés (es una salida del motor) | Traducir en la presentación |

**No hay defectos CRITICAL abiertos.** Hay dos HIGH abiertos (O-01, O-02) que impiden declarar la versión lista para producción; no se aceptaron como riesgo.

## Criterios de liberación (§14 del encargo)

| Criterio | Estado | Evidencia |
|---|---|---|
| Todos los módulos principales conectados | Cumple | Navegación completa; E2E 1–4 (43/43) |
| Operaciones críticas funcionando | Cumple | 234 pruebas de backend; flujos de `TESTING.md` §3 |
| Migraciones ejecutan correctamente | Cumple | Subida, bajada y nueva subida en cada corrida; restaurada y migrada |
| Pruebas críticas pasan | Cumple | `TESTING.md` |
| Aislamiento multi-tenant validado | Cumple | `test_tenant_isolation` + pruebas por módulo; D4-01 corregido |
| Permisos probados | Cumple | `test_rbac`, pruebas 403 por módulo |
| Documentos protegidos | Cumple | `test_security::test_malicious_uploads…` |
| Reportes = datos de origen | Cumple | `test_reports::…reconcile…` |
| Cálculos MSA liberados validados | Cumple | `docs/msa/` y matriz de auditoría; 48 + 8 pruebas |
| Respaldos restaurables | Cumple (Windows) / **No validado** (Docker) | `BACKUP_RESTORE.md` |
| Despliegue privado probado | **No cumple** | O-01 |
| Despliegue en la nube documentado y verificado | **Parcial**: documentado, no verificado | `DEPLOYMENT_CLOUD.md` |
| Documentación actualizada | Cumple | `docs/` |
| Defectos críticos resueltos | Cumple | Ninguno abierto |
| UAT aprobado | **Pendiente** | `UAT.md` |

**Decisión: la versión puede etiquetarse como Release Candidate (`1.0.0-rc.1`), pero NO está lista para producción.**
