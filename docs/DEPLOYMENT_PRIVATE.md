# Instalación privada (infraestructura del cliente)

> **Estado: NO VALIDADO.** Los archivos de `deploy/` están escritos y su sintaxis se validó (YAML y shell), pero **no se han ejecutado con Docker**: el equipo de desarrollo no tiene Docker. Antes de cualquier instalación en un cliente, ejecute este procedimiento completo en un servidor de pruebas y registre la evidencia (lista de verificación del §6).

## 1. Requisitos

- Servidor Linux x86-64 con 4 vCPU, 8 GB de RAM y 50 GB de disco (los documentos crecen con el uso), con Docker Engine 24+ y Docker Compose v2.
- Nombre DNS interno o público para la plataforma (por ejemplo `gagetracker.planta.local`).
- Puertos 80 y 443 hacia el servidor. El Edge Connector solo necesita salida HTTPS hacia ese nombre.

## 2. Instalación

```bash
git clone <repositorio> gagetracker && cd gagetracker
cp deploy/.env.example deploy/.env
# Editar deploy/.env: GT_DOMAIN, POSTGRES_PASSWORD, JWT_SECRET, SECRET_ENCRYPTION_KEY (ver comentarios del archivo).
# Red privada sin DNS público: GT_TLS=internal (CA interna de Caddy; instalar su raíz en los clientes).
docker compose -f deploy/docker-compose.yml --env-file deploy/.env up -d --build
docker compose -f deploy/docker-compose.yml --env-file deploy/.env ps
curl -k https://$GT_DOMAIN/health/ready      # {"status":"ok","database":"ok","schema_revision":"0011_security"}
```

Primera organización: con `ALLOW_SELF_REGISTRATION=true` temporalmente, cree la organización en `https://<dominio>/register`; después vuelva a ponerla en `false` y reinicie `api`. Siga el arranque descrito en `ADMIN_MANUAL.md`.

## 3. Variables

Todas están documentadas en `deploy/.env.example`. Obligatorias: `GT_DOMAIN`, `POSTGRES_USER`, `POSTGRES_PASSWORD`, `JWT_SECRET`, `SECRET_ENCRYPTION_KEY`. Compose se niega a arrancar si falta alguna.

## 4. Actualización

```bash
deploy/backup.sh /srv/backups                       # 1. respaldo (obligatorio)
git fetch --tags && git checkout v<nueva-versión>   # 2. versión
docker compose -f deploy/docker-compose.yml --env-file deploy/.env up -d --build   # 3. el servicio migrate aplica migraciones
curl -k https://$GT_DOMAIN/health/ready             # 4. verificar la revisión de esquema esperada
```

*Rollback*:
1. Volver a la versión anterior (`git checkout v<anterior>`, `up -d --build`).
2. Si la nueva versión aplicó migraciones, ejecutar antes `docker compose ... run --rm migrate alembic downgrade <revisión-anterior>`. Las migraciones 0001–0011 tienen *downgrade* probado en cada corrida de pruebas.
3. Si el *downgrade* no es posible, restaurar el respaldo del paso 1.

## 5. Respaldo y restauración

`deploy/backup.sh` y `deploy/restore.sh`. Ver `BACKUP_RESTORE.md`.

## 6. Lista de verificación para validar la instalación (pendiente de ejecutar)

- [ ] `up -d --build` sin errores; `migrate` termina con código 0.
- [ ] `/health/ready` responde con la revisión 0011.
- [ ] Inicio de sesión, alta de instrumento, carga de certificado PDF y descarga.
- [ ] El *worker* registra `worker_tick`; un webhook de prueba se entrega.
- [ ] `backup.sh` → servidor nuevo → `restore.sh` → conteos y documentos idénticos.
- [ ] Reinicio del servidor: todos los servicios vuelven (`restart: unless-stopped`).
- [ ] Certificado TLS válido para los clientes.
