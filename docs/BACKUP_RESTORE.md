# Respaldo y restauración

## Qué se respalda

1. **Base de datos** PostgreSQL: volcado en formato *custom* (`pg_dump -Fc`).
2. **Documentos** (`STORAGE_DIR`): certificados, informes, fotos y evidencias. Cada archivo está ligado a su registro por SHA-256 (`attachments.sha256`).
3. **Manifiesto**: revisión de esquema y SHA-256 de cada archivo del respaldo.
4. **Fuera del respaldo**, en el gestor de secretos: `JWT_SECRET` y, sobre todo, `SECRET_ENCRYPTION_KEY`. Sin esta última, los secretos de webhook cifrados no se pueden leer.

La base de datos y los documentos deben respaldarse **juntos**: una base sin sus archivos deja referencias rotas.

## Scripts

| Entorno | Respaldo | Restauración | Estado |
|---|---|---|---|
| Windows o servidor sin Docker | `scripts/backup.ps1` | `scripts/restore.ps1` | **Probado** (ver evidencia) |
| Docker (`deploy/`) | `deploy/backup.sh` | `deploy/restore.sh` | Escrito; **no ejecutado** (sin Docker en el equipo de desarrollo) |

```powershell
powershell -File scripts\backup.ps1 -DatabaseUrl "postgresql://USER:***@HOST:5432/gagetracker" -StorageDir D:\gt\storage -OutDir D:\backups
powershell -File scripts\restore.ps1 -BackupDir D:\backups\gagetracker-AAAAMMDD-HHMMSS -DatabaseUrl "postgresql://USER:***@HOST:5432/gagetracker_nueva" -StorageDir D:\gt\storage-nueva
```

Reglas de la restauración:
- Verifica el SHA-256 de cada archivo del respaldo antes de empezar.
- Solo restaura en una base **vacía** y en una carpeta de documentos **vacía**. Nunca escribe sobre datos existentes.
- Ejecuta `ANALYZE` al terminar, para que la base arranque con estadísticas correctas.
- Después hay que ejecutar `alembic upgrade head`, que aplica las migraciones posteriores al respaldo.

## Evidencia de la prueba (2026-10-30)

| Paso | Resultado |
|---|---|
| Respaldo de la base E2E (revisión 0010) con 16 documentos | `database.dump` 357 784 bytes y `storage.zip`, con manifiesto y SHA-256 |
| Restauración en la base nueva `gagetracker_restore` | OK, revisión 0010 restaurada |
| Segunda restauración sobre la misma base | **Rechazada**: «Target database is not empty» |
| Conteos de 11 tablas clave en origen y restaurada (instrumentos, calibraciones, puntos, ejecuciones y observaciones MSA, OOT, auditoría, adjuntos, OT, mediciones, usuarios) | 11 de 11 idénticos (por ejemplo, 434 eventos de auditoría y 270 observaciones MSA) |
| Documentos restaurados contra los originales | 16 de 16 con hash idéntico |
| Cada documento contra el SHA-256 de su fila `attachments` | 16 de 16 coinciden |
| Migración de la base restaurada 0010 → 0011 | OK |
| *Rollback* 0011 → 0010 y nueva migración a 0011 | OK |
| *Worker* contra la base restaurada | Arranca y ejecuta ciclos |
| Respaldo real de la base de desarrollo antes de migrar a 0011 | `gagetracker-20261030-112506` |

## Recomendaciones de operación

- Respaldo diario, con retención de 30 días diarios y 12 mensuales; copia fuera del sitio.
- **Prueba de restauración trimestral** en un entorno aislado, registrando sus evidencias (como la tabla anterior).
- Respaldo inmediato antes de cada actualización de versión.
