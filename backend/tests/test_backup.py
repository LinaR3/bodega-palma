import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from scripts.backup_db import backup
from scripts.restore_sqlite import restore


def test_sqlite_backup_restore_uses_consistent_database_copy(tmp_path):
    original = tmp_path / "active.sqlite3"
    with sqlite3.connect(original) as db:
        db.execute("CREATE TABLE prueba (id INTEGER PRIMARY KEY, valor TEXT)")
        db.execute("INSERT INTO prueba(valor) VALUES ('antes')")
    backup_dir = tmp_path / "external"
    backup_dir.mkdir()
    backup_file = backup(f"sqlite:///{original}", str(backup_dir), 7)
    with sqlite3.connect(original) as db:
        db.execute("UPDATE prueba SET valor='dañado'")
    restore(str(backup_file), str(original))
    with sqlite3.connect(original) as db:
        assert db.execute("SELECT valor FROM prueba").fetchone()[0] == "antes"
        assert db.execute("PRAGMA integrity_check").fetchone()[0] == "ok"


def test_backup_requires_available_destination(tmp_path):
    missing = tmp_path / "no-existe"
    try:
        backup("sqlite:///missing.db", str(missing))
    except RuntimeError:
        pass
    else:
        assert False, "debe fallar si el disco externo no está montado"
