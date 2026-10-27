#!/bin/sh
set -eu
mountpoint -q /mnt/bodega-backups || { echo "Disco externo de backup no está montado" >&2; exit 1; }
test -w /mnt/bodega-backups || { echo "Disco de backup no es escribible" >&2; exit 1; }
cd /opt/bodega
. /etc/bodega/bodega.env
exec /opt/bodega/backend/.venv/bin/python /opt/bodega/scripts/backup_db.py
