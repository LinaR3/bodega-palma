import os
import tempfile

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import Base, get_db
from app.main import app
from app.models import entities  # noqa: F401
from app.core.security import hash_secret
from app.models.entities import Usuario


@pytest.fixture
def db_factory():
    file = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    file.close()
    engine = create_engine(f"sqlite:///{file.name}", connect_args={"check_same_thread": False, "timeout": 30})
    @event.listens_for(engine, "connect")
    def configure_test_sqlite(connection, _record):
        cursor = connection.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.execute("PRAGMA busy_timeout=30000")
        cursor.close()
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    yield factory
    engine.dispose()
    os.unlink(file.name)


@pytest.fixture
def client(db_factory):
    def override():
        db = db_factory()
        try:
            yield db
        finally:
            db.close()
    app.dependency_overrides[get_db] = override
    with TestClient(app) as c:
        db = db_factory()
        db.add(Usuario(nombre="admin-test", rol="ADMIN", credencial_hash=hash_secret("AdminTest123")))
        db.commit()
        db.close()
        response = c.post("/api/auth/login", json={"usuario": "admin-test", "clave": "AdminTest123"})
        assert response.status_code == 200
        c.headers["Authorization"] = f"Bearer {response.json()['token']}"
        yield c
    app.dependency_overrides.clear()


@pytest.fixture
def product_payload():
    return {"codigo_qr": "PAL-000123", "nombre": "Guante industrial", "categoria": "EPP",
            "ubicacion": "Estante A", "unidad_medida": "unidad", "stock_minimo": "2", "stock_maximo": "10"}
