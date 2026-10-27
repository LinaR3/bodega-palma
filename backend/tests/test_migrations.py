import os
import sqlite3
import subprocess
import sys
from pathlib import Path


def test_alembic_upgrade_from_empty_database(tmp_path):
    backend = Path(__file__).resolve().parents[1]
    database = tmp_path / "fresh.sqlite3"
    env = os.environ.copy()
    env["DATABASE_URL"] = f"sqlite:///{database}"
    subprocess.run([sys.executable, "-m", "alembic", "upgrade", "head"], cwd=backend,
                   env=env, check=True, capture_output=True, text=True)
    with sqlite3.connect(database) as db:
        tables = {row[0] for row in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        assert {"productos", "usuarios", "movimientos_inventario", "alertas_pedido",
                "discrepancias", "sesiones", "eventos_auditoria", "alembic_version"} <= tables
        assert db.execute("SELECT version_num FROM alembic_version").fetchone()[0] == "0004_product_media"
