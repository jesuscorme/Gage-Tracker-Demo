#!/usr/bin/env sh
# Restore a backup from deploy/backup.sh into a NEW, empty deployment (fresh volumes).
#   docker compose ... up -d db           # start only the database on fresh volumes
#   deploy/restore.sh /srv/backups/gagetracker-20261030-120000
#   docker compose ... up -d              # migrate runs any newer migrations, then api/worker/web start
# STATUS: written, NOT executed (no Docker on the development machine).
set -eu
SRC="${1:?usage: restore.sh <backup-dir>}"
COMPOSE="docker compose -f $(dirname "$0")/docker-compose.yml --env-file $(dirname "$0")/.env"
( cd "$SRC" && sha256sum -c SHA256SUMS )
TABLES=$($COMPOSE exec -T db sh -c 'psql -At -U "$POSTGRES_USER" "$POSTGRES_DB" -c "select count(*) from information_schema.tables where table_schema='"'"'public'"'"'"')
[ "$TABLES" = "0" ] || { echo "Target database is not empty; refusing to restore" >&2; exit 1; }
$COMPOSE exec -T db sh -c 'pg_restore --no-owner --exit-on-error -U "$POSTGRES_USER" -d "$POSTGRES_DB"' < "$SRC/database.dump"
$COMPOSE exec -T db sh -c 'psql -q -U "$POSTGRES_USER" "$POSTGRES_DB" -c ANALYZE'
$COMPOSE run --rm --no-deps -T --entrypoint sh api -c 'cd /data/storage && tar -xzf -' < "$SRC/storage.tar.gz"
echo "Restored $(cat "$SRC/manifest.txt")"
