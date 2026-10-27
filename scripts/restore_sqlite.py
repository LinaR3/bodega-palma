#!/usr/bin/env python3
"""Validate a backup and atomically restore it to a stopped SQLite database."""
import os
import sqlite3
import sys
import tempfile
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path


def restore(backup_path: str, destination_path: str) -> Path:
    backup_file, destination = Path(backup_path), Path(destination_path)
    if not backup_file.is_file():
        raise FileNotFoundError(backup_file)
    if destination.with_name(destination.name + "-wal").exists() or destination.with_name(destination.name + "-shm").exists():
        raise RuntimeError("Hay archivos WAL/SHM: detenga el servicio antes de restaurar")
    with closing(sqlite3.connect(f"file:{backup_file}?mode=ro", uri=True)) as source:
        if source.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
            raise RuntimeError("El backup no pasó integrity_check")
        with tempfile.NamedTemporaryFile(dir=destination.parent, suffix=".restore", delete=False) as temp:
            temp_path = Path(temp.name)
        try:
            with closing(sqlite3.connect(temp_path)) as target:
                source.backup(target)
                if target.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
                    raise RuntimeError("La copia restaurada no pasó integrity_check")
            if destination.exists():
                safety = destination.with_name(f"{destination.name}.pre-restore-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}")
                with closing(sqlite3.connect(f"file:{destination}?mode=ro", uri=True)) as current, closing(sqlite3.connect(safety)) as safety_db:
                    current.backup(safety_db)
                os.chmod(safety, 0o600)
            os.replace(temp_path, destination)
            os.chmod(destination, 0o600)
            return destination
        finally:
            temp_path.unlink(missing_ok=True)


if __name__ == "__main__":
    if len(sys.argv) != 3:
        raise SystemExit("Uso: python restore_sqlite.py BACKUP.sqlite3 DESTINO.sqlite3")
    print(restore(sys.argv[1], sys.argv[2]))
