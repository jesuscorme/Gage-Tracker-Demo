# Notas de versión

## 1.0.0-rc.1 — Release Candidate (2026-10-30)

> Versión **candidata**, no liberada a producción. Antes de liberar deben cumplirse los criterios pendientes del informe de cierre (`PROGRESS_REPORT_04.md` §17–18): validar el despliegue con Docker, ejecutar CI, UAT con usuarios y una revisión de seguridad externa.

### Nuevo en este bloque
- **Tablero ejecutivo**: 16 indicadores y 10 visualizaciones, con filtros por planta, departamento, tipo, estado, responsable y periodo; totales conciliados con los datos de origen.
- **Centro de reportes**: 22 reportes de metrología, MSA, laboratorio y OOT en PDF, Excel, CSV y JSON, con identificación, permisos y auditoría de descarga. El reporte MSA por estudio se emite ahora en español o inglés.
- **Seguridad**:
  - revocación de sesiones (cerrar en todos los dispositivos) y cambio de contraseña;
  - restablecimiento por enlace de un solo uso;
  - bloqueo por fuerza bruta;
  - cifrado en reposo de secretos de webhook;
  - cabeceras de seguridad y auditoría de descargas.
- **Corrección de aislamiento** (alta): referencias a plantas de otra organización en escritura.
- **Dependencias** actualizadas sin vulnerabilidades conocidas: FastAPI 0.162, starlette 1.10, cryptography 50.0.2, python-multipart 0.0.32, fpdf2 2.9.0, Next.js 15.5.28.
- **Operación**:
  - *worker* separado (`python -m app.worker`);
  - respaldo y restauración probados;
  - paquete de despliegue (`deploy/`) y pipeline de CI (`.github/workflows/ci.yml`), ambos sin ejecutar todavía;
  - instancia demo reproducible.
- **Calidad**:
  - regresión estadística *golden* de los 8 métodos MSA;
  - pruebas de concurrencia y rendimiento;
  - lint con ruff.
- Migración `0011_security`.

### Bloques anteriores
- **0.8**: MSA y motor estadístico, OOT, integraciones, configuración y cumplimiento (`PROGRESS_REPORT_03.md`).
- **0.5**: calibración, patrones, competencias y laboratorio (`PROGRESS_REPORT_02.md`).
- **0.2**: plataforma y Gage Management (`PROGRESS_REPORT_01.md`).

## Política de versiones

- **SemVer**:
  - MAJOR: cambios incompatibles de API v1 o migraciones sin *downgrade*;
  - MINOR: funciones nuevas compatibles;
  - PATCH: correcciones.
  - Preliminares: `-rc.N`.
- **Tags**: `vX.Y.Z` o `vX.Y.Z-rc.N` sobre `main`. El pipeline construye las imágenes `gagetracker-api:X.Y.Z` y `gagetracker-web:X.Y.Z` desde el tag.
- **Ramas**:
  - `main` siempre estable y con CI en verde;
  - ramas `feature/*` mediante pull request con revisión;
  - `release/X.Y` para estabilizar;
  - `hotfix/*` desde el tag liberado.
- **Despliegue**: respaldo → migraciones → API → *worker* → verificación de `/health/ready` (`DEPLOYMENT_PRIVATE.md` §4).
- **Rollback**: versión anterior y `alembic downgrade` (probado en las migraciones 0001–0011), o restauración del respaldo previo.
