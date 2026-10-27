#!/bin/sh
set -eu
cd /opt/bodega/deploy
. ./.env
mountpoint -q "${BACKUP_HOST_DIR:?BACKUP_HOST_DIR requerido}" || {
  echo "Disco de respaldo no montado en $BACKUP_HOST_DIR" >&2
  exit 1
}
test -w "$BACKUP_HOST_DIR" || { echo "Disco de respaldo no es escribible" >&2; exit 1; }
docker compose -f compose.yaml exec -T api python /app/backend/scripts/backup_db.py
