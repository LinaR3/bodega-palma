from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.models.entities import Discrepancia, MovimientoInventario, Producto, AlertaPedido, EstadoAlerta
from app.schemas.inventory import MovimientoCreate
from app.services.inventory import estado_stock, registrar_movimiento


@pytest.mark.parametrize(("stock", "expected"), [
    (Decimal("2"), "CRITICO"), (Decimal("1"), "CRITICO"),
    (Decimal("2.1"), "PRECAUCION"), (Decimal("2.4"), "PRECAUCION"),
    (Decimal("2.41"), "OPTIMO"),
])
def test_semaforo(stock, expected):
    assert estado_stock(stock, Decimal("2")) == expected


def test_create_product_validates_bounds(client, product_payload):
    assert client.post("/api/productos", json=product_payload).status_code == 201
    invalid = dict(product_payload, codigo_qr="PAL-000124", stock_minimo="10", stock_maximo="10")
    assert client.post("/api/productos", json=invalid).status_code == 422


def test_qr_unique(client, product_payload):
    assert client.post("/api/productos", json=product_payload).status_code == 201
    assert client.post("/api/productos", json=product_payload).status_code == 409


def create_product(db_factory, stock=Decimal("0")):
    db = db_factory()
    p = Producto(codigo_qr=f"PAL-{uuid4().hex[:8].upper()}", nombre="Producto", categoria="General",
                 ubicacion="A", unidad_medida="unidad", stock_actual=stock,
                 stock_minimo=Decimal("2"), stock_maximo=Decimal("10"))
    db.add(p); db.commit(); db.refresh(p)
    pid = p.id; db.close()
    return pid


def movement(uuid, product_id, delta, kind="SALIDA", ref=None):
    return MovimientoCreate(uuid=uuid, producto_id=product_id, tipo=kind, cantidad_cambio=Decimal(delta),
                            motivo="Prueba de inventario", usuario_nombre="Bodega", dispositivo="test",
                            movimiento_referenciado_id=ref)


def test_delta_idempotent_and_suggests_to_maximum(db_factory):
    pid = create_product(db_factory, Decimal("5"))
    db = db_factory()
    payload = movement(uuid4(), pid, "-3")
    first, replay = registrar_movimiento(db, payload)
    assert replay is False and first.stock_resultante == 2
    same, replay = registrar_movimiento(db, payload)
    assert replay is True and same.id == first.id
    p = db.get(Producto, pid)
    alerts = db.scalars(select(AlertaPedido).where(AlertaPedido.producto_id == pid)).all()
    assert p.stock_actual == 2
    assert len(alerts) == 1 and alerts[0].cantidad_sugerida == 8
    db.close()


def test_negative_stock_accepted_and_discrepancy_created(db_factory):
    pid = create_product(db_factory)
    db = db_factory()
    movement_row, _ = registrar_movimiento(db, movement(uuid4(), pid, "-1"))
    assert movement_row.stock_resultante == -1
    assert db.scalar(select(Discrepancia).where(Discrepancia.movimiento_id == movement_row.id))
    db.close()


def test_inventory_movements_cannot_be_edited_or_deleted(db_factory):
    pid = create_product(db_factory, Decimal("5"))
    db = db_factory()
    row, _ = registrar_movimiento(db, movement(uuid4(), pid, "-1"))
    row.motivo = "alterado"
    with pytest.raises(ValueError, match="inmutables"):
        db.commit()
    db.rollback()
    row = db.get(MovimientoInventario, row.id)
    db.delete(row)
    with pytest.raises(ValueError, match="inmutables"):
        db.commit()
    db.rollback(); db.close()


def test_fractional_delta_rejected():
    with pytest.raises(ValueError):
        movement(uuid4(), 1, "-0.5")


def test_adjustment_and_full_annulment(db_factory):
    pid = create_product(db_factory, Decimal("5"))
    db = db_factory()
    original, _ = registrar_movimiento(db, movement(uuid4(), pid, "-2"))
    partial, _ = registrar_movimiento(db, movement(uuid4(), pid, "1", "AJUSTE", original.id))
    assert partial.stock_resultante == 4
    reversal, _ = registrar_movimiento(db, movement(uuid4(), pid, "2", "ANULACION", original.id))
    assert reversal.stock_resultante == 6
    with pytest.raises(Exception):
        registrar_movimiento(db, movement(uuid4(), pid, "2", "ANULACION", original.id))
    db.close()


def test_same_uuid_concurrent_retries_only_apply_once(db_factory):
    pid = create_product(db_factory, Decimal("10"))
    ident = uuid4()
    payload = movement(ident, pid, "-1")

    def apply():
        db = db_factory()
        try:
            return registrar_movimiento(db, payload)
        finally:
            db.close()
    with ThreadPoolExecutor(max_workers=8) as pool:
        result = list(pool.map(lambda _: apply(), range(16)))
    check = db_factory()
    assert check.get(Producto, pid).stock_actual == 9
    assert check.scalar(select(MovimientoInventario).where(MovimientoInventario.uuid == ident))
    assert sum(1 for _, replay in result if not replay) == 1
    check.close()


def test_parallel_deltas_preserve_atomic_total(db_factory):
    pid = create_product(db_factory, Decimal("50"))

    def apply(i):
        db = db_factory()
        try:
            return registrar_movimiento(db, movement(uuid4(), pid, "-1"))[0].stock_resultante
        finally:
            db.close()
    with ThreadPoolExecutor(max_workers=8) as pool:
        list(pool.map(apply, range(20)))
    db = db_factory()
    assert db.get(Producto, pid).stock_actual == 30
    db.close()


def test_order_receipt_is_inventory_entry_and_idempotent(client, product_payload):
    made = client.post("/api/productos", json=product_payload).json()
    entered = client.post("/api/movimientos", json={"uuid": str(uuid4()), "producto_id": made["id"],
        "tipo": "ENTRADA", "cantidad_cambio": 2, "motivo": "Carga inicial"})
    assert entered.status_code == 200
    # Two-unit exit leaves the item exactly at its minimum and creates one suggestion.
    client.post("/api/movimientos", json={"uuid": str(uuid4()), "producto_id": made["id"],
        "tipo": "SALIDA", "cantidad_cambio": -2, "motivo": "Consumo"})
    alert = client.get("/api/alertas").json()[0]
    assert alert["cantidad_sugerida"] == "10.000"
    approved = client.post(f"/api/alertas/{alert['id']}/transicion", json={"estado": "APROBADO"})
    assert approved.status_code == 200
    ordered = client.post(f"/api/alertas/{alert['id']}/transicion", json={"estado": "PEDIDO", "cantidad_pedida": 10})
    assert ordered.status_code == 200
    receipt_uuid = str(uuid4())
    received = client.post(f"/api/alertas/{alert['id']}/transicion", json={"estado": "RECIBIDO", "cantidad_recibida": 4,
        "uuid_movimiento": receipt_uuid})
    assert received.status_code == 200 and received.json()["estado"] == "PEDIDO"
    again = client.post(f"/api/alertas/{alert['id']}/transicion", json={"estado": "RECIBIDO", "cantidad_recibida": 4,
        "uuid_movimiento": receipt_uuid})
    assert again.status_code == 200
    assert len([m for m in client.get("/api/movimientos").json() if m["uuid"] == receipt_uuid]) == 1
    end = client.post(f"/api/alertas/{alert['id']}/transicion", json={"estado": "RECIBIDO", "cantidad_recibida": 6,
        "uuid_movimiento": str(uuid4())})
    assert end.json()["estado"] == "RECIBIDO"
    product = client.get("/api/productos").json()[0]
    assert product["stock_actual"] == "10.000"


def test_cancelled_suggestion_does_not_reappear_in_same_transition(client, product_payload):
    product = client.post("/api/productos", json=product_payload).json()
    client.post("/api/movimientos", json={"uuid": str(uuid4()), "producto_id": product["id"],
        "tipo": "SALIDA", "cantidad_cambio": -1, "motivo": "Consumo"})
    alert = client.get("/api/alertas").json()[0]
    cancelled = client.post(f"/api/alertas/{alert['id']}/transicion", json={"estado": "CANCELADO"})
    assert cancelled.status_code == 200 and cancelled.json()["estado"] == "CANCELADO"
    assert len(client.get("/api/alertas").json()) == 1
