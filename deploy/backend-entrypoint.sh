#!/bin/sh
set -eu
mkdir -p /data/logs
chown -R bodega:bodega /data
exec gosu bodega "$@"
