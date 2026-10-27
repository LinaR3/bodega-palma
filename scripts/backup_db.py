#!/usr/bin/env python3
"""Consistent nightly SQLite backup via sqlite3.Connection.backup, or pg_dump."""
import os
import sqlite3
import subprocess
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy.engine import make_url


def backup(database_url: str, destination_dir: str, retain_days: int = 30) -> Path:
    target_dir = Path(destination_dir)
    if not target_dir.is_dir() or not os.access(target_dir, os.W_OK):
        raise RuntimeError(f"Directorio de backup no disponible/escribible: {target_dir}")
    if retain_days < 1:
        raise ValueError("retain_days debe ser al menos 1")
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    url = make_url(database_url)
    if url.get_backend_name() == "sqlite":
        if not url.database or url.database == ":memory:":
            raise ValueError("DATABASE_URL debe apuntar a un archivo SQLite persistente")
        source = Path(url.database)
        if not source.is_absolute():
            source = Path.cwd() / source
        if not source.exists():
            raise FileNotFoundError(source)
        destination = target_dir / f"bodega-{stamp}.sqlite3"
        with closing(sqlite3.connect(f"file:{source}?mode=ro", uri=True, timeout=30)) as src:
            with closing(sqlite3.connect(destination)) as dst:
                src.backup(dst)
                result = dst.execute("PRAGMA integrity_check").fetchone()[0]
                if result != "ok":
                    destination.unlink(missing_ok=True)
                    raise RuntimeError(f"integrity_check falló: {result}")
    elif url.get_backend_name() in {"postgresql", "postgres"}:
        destination = target_dir / f"bodega-{stamp}.dump"
        # For production, use PGPASSFILE or another libpq credential mechanism.
        subprocess.run(["pg_dump", "--format=custom", "--no-owner", "--file", str(destination), "--dbname", database_url], check=True)
    else:
        raise ValueError(f"Motor no soportado: {url.get_backend_name()}")
    os.chmod(destination, 0o600)
    cutoff = datetime.now(timezone.utc).timestamp() - retain_days * 86400
    for item in target_dir.glob("bodega-*"):
        if item != destination and item.is_file() and item.stat().st_mtime < cutoff:
            item.unlink()
    return destination


if __name__ == "__main__":
    db_url = os.environ.get("DATABASE_URL", "sqlite:///./bodega.db")
    backup_dir = os.environ.get("BACKUP_DIR", "/mnt/bodega-backups")
    retention = int(os.environ.get("BACKUP_RETENTION_DAYS", "30"))
    print(backup(db_url, backup_dir, retention))
