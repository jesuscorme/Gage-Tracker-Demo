# Seguridad

Revisión integral de seguridad del bloque 4 (2026-10-30). Es una revisión interna de código y pruebas, **no** una auditoría ni una prueba de penetración externas.

## 1. Autenticación

| Control | Implementación | Evidencia |
|---|---|---|
| Contraseñas | bcrypt (costo ≥ 12 en producción); al menos 10 caracteres combinando letras con números o símbolos; máximo 72 bytes | `test_platform`, `test_security::…revoke_tokens` |
| Sesiones | JWT HS256 con caducidad (60 min por defecto) y versión de token por usuario | `test_security` |
| Cierre de sesión | El cliente borra su token. «Cerrar sesión en todos los dispositivos» incrementa la versión de token y revoca todo lo emitido | `test_logout_all…` |
| Cambio de contraseña | Exige la contraseña actual y revoca las demás sesiones | `test_logout_all…`, E2E 4 |
| Recuperación | El administrador genera un enlace de un solo uso que caduca en 60 min. Solo se guarda el SHA-256 del token. El enlace no se envía por correo (no hay SMTP) | `test_brute_force_lockout_and_admin_reset`, E2E 4 |
| Fuerza bruta | 5 fallos en 15 min bloquean la cuenta (429), aunque luego se use la contraseña correcta. Un restablecimiento levanta el bloqueo | ídem |
| Llaves API | `gtk_<prefijo>_<secreto>`. Solo se guarda el SHA-256, se compara en tiempo constante, son revocables y tienen caducidad. El rol nunca es administrador | `test_integrations` |
| MFA / SSO (OIDC) | **No implementado** | Pendiente para producción |

## 2. Autorización

- **RBAC** con 48 permisos y 8 roles; la matriz por rol está probada (`test_rbac`).
- **Permisos por acción**: cada endpoint declara su permiso.
- **Autorizaciones personales** para actividades técnicas (calibrar, revisar, aprobar, laboratorio, inspección, MSA).
- **Matriz de aprobación configurable** para calibración, MSA y OOT.
- **Segregación de funciones**: quien ejecuta no revisa ni aprueba.
- **Alcance por planta**: un usuario con plantas asignadas solo ve y escribe en ellas.

## 3. Multi-tenancy

| Vector | Prueba |
|---|---|
| URL o id de otra organización | 404 en todos los módulos (`test_tenant_isolation`, pruebas de aislamiento por módulo) |
| Referencias cruzadas en escritura (planta de otra organización) | **Defecto encontrado y corregido** en este bloque (alto): estudios MSA, criterios y dispositivos aceptaban un `plant_id` ajeno. Prueba de regresión `test_records_cannot_reference_another_organizations_plant` |
| API (llaves) | Cada llave queda limitada a su organización y plantas (`test_exchange_contracts_respect_permissions_and_plant_scope`) |
| Exportaciones y reportes | `test_report_permissions_and_tenant_scope`; la exportación de cumplimiento valida el instrumento |
| Archivos adjuntos | Descarga y carga cruzadas → 404 (`test_malicious_uploads_and_cross_tenant_documents`) |
| Procesos de fondo | Webhooks, escalamientos y barrido de vencidos operan por organización. Las entregas solo van a los endpoints de la organización dueña del evento |
| Tablero | Un filtro de planta ajena → 404 (`test_dashboard`) |

## 4. Protección de información

- **Archivos**:
  - Lista blanca de extensiones, validación de *magic bytes*, tamaño máximo configurable y almacenamiento con nombre por hash.
  - Los documentos aprobados quedan bloqueados (no se reemplazan en silencio).
  - Toda descarga queda auditada (`document.downloaded`) y se sirve con `Cache-Control: private, no-store`.
- **Secretos**:
  - En producción la aplicación no arranca sin `JWT_SECRET` fuerte ni `SECRET_ENCRYPTION_KEY`.
  - Los secretos de webhook se cifran en reposo (Fernet) y se muestran una sola vez.
  - Los archivos `.env` de ejemplo no contienen secretos reales.
- **Tránsito**:
  - HTTPS en el proxy (Caddy) con HSTS.
  - Cabeceras `X-Content-Type-Options`, `X-Frame-Options`, `Referrer-Policy` y `Content-Security-Policy` en la API.
- **Logs**:
  - Una línea por petición (método, ruta, estado, duración, request id), sin cuerpos, tokens ni contraseñas.
  - Los errores 500 no exponen detalles internos.
- **Webhooks**:
  - Firma HMAC-SHA256.
  - En producción solo https y sin IP privadas literales. **Pendiente**: protección anti-SSRF con resolución DNS.

## 5. Auditoría

`audit_events` registra usuario, fecha y hora, entidad, acción, valores anteriores y nuevos, motivo, request id e IP (origen). Es de solo inserción por trigger: ni la aplicación ni un usuario de base de datos con permisos de la aplicación pueden modificarla. Las operaciones críticas auditadas incluyen:
- inicio de sesión (éxito, fallo y bloqueo), cambio y restablecimiento de contraseña, cierre global;
- cambios de instrumentos, transiciones y liberaciones;
- calibraciones, MSA, OOT, configuración y criterios;
- reportes generados, descargas de documentos y exportaciones de cumplimiento.

## 6. Dependencias

Auditoría del 2026-10-30. Había vulnerabilidades conocidas en:
- Next.js (crítica);
- cryptography, starlette, python-multipart, fpdf2;
- postcss y sharp (altas).

Todas se corrigieron con estas actualizaciones:
- FastAPI 0.115 → 0.162 y starlette 0.46 → 1.10;
- cryptography 50.0.2, python-multipart 0.0.32, fpdf2 2.9.0;
- Next.js 15.5.4 → 15.5.28;
- postcss 8.5.32 mediante `overrides`.

Resultado: `pip-audit` y `npm audit` sin hallazgos. Con las versiones nuevas pasan las 234 pruebas de backend (corrida final) y las 4 suites E2E.

## 7. Riesgos abiertos

| Riesgo | Severidad | Tratamiento propuesto |
|---|---|---|
| Sin MFA ni SSO | Media | Implementar OIDC/MFA antes de exponer la plataforma a Internet |
| El bloqueo por cuenta permite que un atacante bloquee a un usuario conocido | Media | Agregar límite por IP en el proxy (Caddy `rate_limit` o WAF) |
| Sin envío de correo: el restablecimiento depende del administrador | Baja | SMTP configurable |
| Protección anti-SSRF de webhooks solo literal | Media | Resolver DNS y bloquear rangos privados antes de cada envío |
| `postcss` forzado por `overrides` dentro de Next 15 | Baja | Eliminar el override al migrar a Next 16 |
| Sin prueba de penetración externa | Media | Contratar antes de la liberación productiva |
