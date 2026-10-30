# Manual de administración

## Arranque de una organización

1. **Organización y plantas**: *Organización y plantas*. Defina la zona horaria y los días de anticipación para «por vencer».
2. **Usuarios**: *Usuarios → + Nuevo*, con rol y plantas (vacío = todas).

   | Rol | Uso típico |
   |---|---|
   | org_admin | Administra todo |
   | metrology_manager | Gestiona metrología, revisa y aprueba |
   | metrology_technician | Ejecuta calibraciones y estudios |
   | lab_technician | Ejecuta órdenes |
   | requester | Solicita servicios |
   | auditor | Solo lectura, incluida la auditoría |
   | viewer | Consulta |
   | edge_agent | Solo para conectores |

3. **Autorizaciones personales** (*Competencias → Autorizaciones*): sin ellas no se puede ejecutar, revisar ni aprobar. Las actividades son INTERNAL_CALIBRATION, ROUTINE_VERIFICATION, TECHNICAL_REVIEW, APPROVAL, LAB_SERVICE, DIMENSIONAL_INSPECTION y MSA_EVALUATION.
4. **Tipos de instrumento**, **patrones** con su certificado y **servicios del laboratorio** (*Configuración técnica*).
5. **Criterios de aceptación MSA** (*MSA → Criterios MSA*): partir de una plantilla, revisar la fuente y que **otra persona** los apruebe.
6. Opcional, en **Configuración avanzada**: campos personalizados, formularios, workflows, matrices de aprobación, reglas y ajustes OOT. Los workflows, matrices y reglas requieren la aprobación de un segundo usuario.

## Operación de cuentas

- **Restablecer contraseña**: *Usuarios → Generar enlace de restablecimiento*. Entregue el enlace por un canal seguro; es de un solo uso, caduca en 60 minutos y cierra todas las sesiones del usuario.
- **Bloqueos**: 5 intentos fallidos en 15 minutos. Se levanta con un restablecimiento o esperando el tiempo de bloqueo. Parámetros: `LOGIN_MAX_FAILURES` y `LOGIN_LOCKOUT_MINUTES`.
- **Bajas**: desactivar al usuario conserva su historial; nunca se borra.

## Integraciones

En *Integraciones*: clientes API (la llave se muestra una sola vez), webhooks (el secreto se muestra una vez y se guarda cifrado), dispositivos y simulador, importaciones e historial de eventos. Detalle en `docs/integrations/README.md`.

## Mantenimiento

| Tarea | Cómo |
|---|---|
| Respaldo y restauración | `BACKUP_RESTORE.md` |
| Actualización y *rollback* | `DEPLOYMENT_PRIVATE.md` §4 |
| Demo | `powershell -File scripts/demo-reset.ps1` reconstruye `gagetracker_demo` con datos ficticios marcados [DEMO]; usuarios `@demo.example.com`, contraseña en `DEMO_PASSWORD` |
| Tareas de fondo | El servicio `worker` (o `SCHEDULER_ENABLED=true` en una instalación de un solo proceso) entrega webhooks, escalamientos y avisos de vencidos |
| Rendimiento | Después de cargas masivas o restauraciones, `ANALYZE` (`DATABASE.md`) |

## Solución de problemas

| Síntoma | Causa probable | Acción |
|---|---|---|
| «no tiene autorización vigente para …» | Falta la autorización personal | *Competencias → Autorizaciones* |
| «La matriz de aprobación no permite…» | El rol no figura en la matriz activa | Revisar o editar la matriz |
| El instrumento no se puede liberar | Caso OOT abierto con restricción | Liberar desde el caso, tras una calibración aceptable |
| 429 al iniciar sesión | Bloqueo por intentos | Generar un enlace de restablecimiento |
| `/health/ready` con `database != ok` | Base caída o credenciales | Revisar el servicio `db` y `DATABASE_URL` |
| El tablero va lento tras una restauración | Estadísticas | `ANALYZE` |
| La aplicación no arranca en producción | Falta `JWT_SECRET` fuerte o `SECRET_ENCRYPTION_KEY` | Configurar los secretos |
