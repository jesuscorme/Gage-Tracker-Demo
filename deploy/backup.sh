#!/usr/bin/env sh
# Backup of a Docker deployment: database dump + document volume + manifest with SHA-256.
#   deploy/backup.sh /srv/backups
# STATUS: written, NOT executed (no Docker on the development machine). The equivalent
# Windows scripts (scripts/backup.ps1, scripts/restore.ps1) were executed and verified.
set -eu
OUT="${1:?usage: backup.sh <output-dir>}"
STAMP=$(date +%Y%m%d-%H%M%S)
DEST="$OUT/gagetracker-$STAMP"
COMPOSE="docker compose -f $(dirname "$0")/docker-compose.yml --env-file $(dirname "$0")/.env"
mkdir -p "$DEST"
$COMPOSE exec -T db sh -c 'pg_dump --format=custom --no-owner -U "$POSTGRES_USER" "$POSTGRES_DB"' > "$DEST/database.dump"
$COMPOSE run --rm --no-deps -T --entrypoint sh api -c 'cd /data/storage && tar -czf - .' > "$DEST/storage.tar.gz"
REV=$($COMPOSE exec -T db sh -c 'psql -At -U "$POSTGRES_USER" "$POSTGRES_DB" -c "select version_num from alembic_version"')
( cd "$DEST" && sha256sum database.dump storage.tar.gz > SHA256SUMS && echo "schema_revision=$REV" > manifest.txt )
echo "$DEST"
