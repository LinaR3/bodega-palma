import csv
import io
from decimal import Decimal
from uuid import uuid4

from app.models.entities import Usuario
from app.schemas.inventory import ProductoCreate
from app.services.files import qr_labels_pdf, read_catalog, suggestions_pdf, suggestions_xlsx


def test_login_roles_and_admin_revokes_bodeguero_session(client, db_factory):
    made = client.post("/api/auth/usuarios", json={"nombre": "bodega", "rol": "BODEGUERO", "clave": "4821"})
    assert made.status_code == 201
    login = client.post("/api/auth/login", json={"usuario": "bodega", "clave": "4821", "dispositivo": "android-1"})
    assert login.status_code == 200
    operator_token = login.json()["token"]
    assert client.post("/api/auth/usuarios", json={"nombre": "otro", "rol": "BODEGUERO", "clave": "4821"}).status_code == 201
    # Admin route works; later revoke target sessions and verify the bearer token is dead.
    session = db_factory()
    try:
        operator = session.query(Usuario).filter_by(nombre="bodega").first()
        response = client.post(f"/api/auth/usuarios/{operator.id}/revocar-sesiones")
        assert response.status_code == 204
    finally:
        session.close()
    client.headers["Authorization"] = f"Bearer {operator_token}"
    assert client.get("/api/productos").status_code == 401


def test_catalog_csv_reports_row_errors(product_payload):
    fields = list(product_payload.keys())
    out = io.StringIO(); writer = csv.DictWriter(out, fieldnames=fields); writer.writeheader()
    writer.writerow(product_payload)
    writer.writerow(dict(product_payload, codigo_qr="invalid spaces"))
    rows, errors = read_catalog(out.getvalue().encode(), "catalogo.csv")
    assert len(rows) == 1
    assert errors and errors[0]["fila"] == 3


def test_pdf_and_excel_exports_are_generated(client, product_payload):
    assert client.post("/api/productos", json=product_payload).status_code == 201
    pdf = client.get("/api/etiquetas.pdf")
    xlsx = client.get("/api/exportar/pedidos.xlsx")
    order_pdf = client.get("/api/exportar/pedidos.pdf")
    assert pdf.status_code == xlsx.status_code == order_pdf.status_code == 200
    assert pdf.content.startswith(b"%PDF")
    assert order_pdf.content.startswith(b"%PDF")
    assert xlsx.content.startswith(b"PK")


def test_product_schema_rejects_fractional_stock_configuration():
    import pytest
    with pytest.raises(ValueError):
        ProductoCreate(codigo_qr="PAL-001234", nombre="Envase", categoria="X", ubicacion="A",
                       unidad_medida="unidad", stock_minimo="0.5", stock_maximo="2")


def test_import_catalog_commits_valid_rows_and_reports_invalid_ones(client):
    import io
    content = ("codigo_qr,nombre,categoria,ubicacion,unidad_medida,stock_minimo,stock_maximo\n"
               "PAL-009001,Motor A,Motores,Estante 1,unidad,1,5\n"
               "MAL CODIGO,Motor B,Motores,Estante 2,unidad,5,5\n")
    response = client.post("/api/catalogo/importar", files={"file": ("catalogo.csv", io.BytesIO(content.encode()), "text/csv")})
    assert response.status_code == 200
    payload = response.json()
    assert payload["insertados"] == 1 and len(payload["errores"]) == 1
    assert "reporte_csv" in payload and "fila,error" in payload["reporte_csv"] and "3," in payload["reporte_csv"]


def test_import_catalog_supports_xlsx(client):
    from openpyxl import Workbook
    wb = Workbook(); ws = wb.active
    ws.append(["codigo_qr", "nombre", "categoria", "ubicacion", "unidad_medida", "stock_minimo", "stock_maximo"])
    ws.append(["PAL-009002", "Bomba", "Motores", "Estante 3", "unidad", 1, 4])
    content = io.BytesIO(); wb.save(content); content.seek(0)
    response = client.post("/api/catalogo/importar", files={"file": ("catalogo.xlsx", content, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")})
    assert response.status_code == 200 and response.json()["insertados"] == 1


def test_import_excel_keeps_product_description_photo_and_initial_stock_as_movement(client, db_factory):
    from openpyxl import Workbook
    from app.models.entities import MovimientoInventario, Producto
    wb = Workbook(); ws = wb.active
    ws.append(["codigo_qr", "nombre", "categoria", "ubicacion", "unidad_medida", "stock_minimo", "stock_maximo", "descripcion", "foto_url", "stock_inicial"])
    ws.append(["PAL-009110", "Envases plásticos", "Insumos", "Estante B1", "unidad", 2, 10,
               "Envases completos y sellados.", "/productos/envase.jpg", 7])
    content = io.BytesIO(); wb.save(content); content.seek(0)
    response = client.post("/api/catalogo/importar", files={"file": ("muestra.xlsx", content,
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")})
    assert response.status_code == 200 and response.json()["insertados"] == 1
    products = client.get("/api/productos?q=Envases").json()
    assert products[0]["stock_actual"] == "7.000"
    assert products[0]["descripcion"] == "Envases completos y sellados."
    assert products[0]["foto_url"] == "/productos/envase.jpg"
    db = db_factory()
    try:
        movement = db.query(MovimientoInventario).filter_by(producto_id=products[0]["id"]).one()
        assert movement.tipo == "ENTRADA" and movement.cantidad_cambio == 7
    finally:
        db.close()


def test_demo_seed_catalog_contains_only_safe_whole_items():
    from pathlib import Path
    from app.demo_catalog import DEMO_PRODUCTS
    public = Path(__file__).resolve().parents[2] / "frontend" / "public"
    assert len(DEMO_PRODUCTS) == 10
    assert all(item["stock_inicial"] == item["stock_inicial"].to_integral_value() for item in DEMO_PRODUCTS)
    assert all(item["foto_url"].startswith("/productos/") and item["descripcion"] for item in DEMO_PRODUCTS)
    assert all((public / item["foto_url"].lstrip("/")).is_file() for item in DEMO_PRODUCTS)
    prohibited = ("tornillo", "tuerca", "cuchillo", "cuchilla", "aguja", "punzante")
    assert not any(any(word in (item["nombre"] + " " + item["descripcion"]).lower() for word in prohibited)
                   for item in DEMO_PRODUCTS)


def test_downloadable_sample_excel_can_be_imported_and_adds_ten_products(client):
    example = client.get("/api/catalogo/ejemplo.xlsx")
    assert example.status_code == 200 and example.content.startswith(b"PK")
    imported = client.post("/api/catalogo/importar", files={"file": ("catalogo-ejemplo.xlsx", example.content,
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")})
    assert imported.status_code == 200
    assert imported.json()["insertados"] == 10
    products = client.get("/api/productos").json()
    assert {p["codigo_qr"] for p in products} == {f"PAL-009{n}" for n in range(101, 111)}
    assert all(p["descripcion"] and p["foto_url"] for p in products)
    assert {p["stock_actual"] for p in products} == {"3.000", "4.000", "5.000", "6.000", "7.000", "8.000", "10.000", "12.000", "15.000"}


def test_demo_seed_adds_initial_stock_as_audited_movements_and_is_idempotent(db_factory, monkeypatch):
    from app import seed_demo
    from app.models.entities import MovimientoInventario, Producto
    monkeypatch.setattr(seed_demo, "SessionLocal", db_factory)
    assert seed_demo.seed_demo() == 10
    assert seed_demo.seed_demo() == 0
    db = db_factory()
    try:
        assert db.query(Producto).count() == 10
        assert db.query(MovimientoInventario).count() == 10
        assert sum((p.stock_actual for p in db.query(Producto).all()), Decimal(0)) == Decimal(80)
    finally:
        db.close()


def test_admin_can_create_manual_purchase_order_without_critical_stock(client, product_payload):
    product = client.post("/api/productos", json=product_payload).json()
    created = client.post("/api/pedidos/manuales", json={"producto_id": product["id"], "cantidad": 6,
        "observacion": "Mantenimiento programado"})
    assert created.status_code == 201
    order = created.json()
    assert order["estado"] == "SUGERIDO" and order["es_manual"] is True
    assert order["cantidad_sugerida"] == "6.000" and order["observacion"] == "Mantenimiento programado"
    dashboard = client.get("/api/dashboard/resumen").json()
    assert dashboard["alertas"][0]["es_manual"] is True
    # A second manual request updates the open draft instead of duplicating it.
    updated = client.post("/api/pedidos/manuales", json={"producto_id": product["id"], "cantidad": 4})
    assert updated.status_code == 201 and updated.json()["id"] == order["id"]
    assert updated.json()["cantidad_sugerida"] == "4.000"
    assert len(client.get("/api/alertas").json()) == 1


def test_manual_order_rejects_fractional_quantity_and_existing_in_transit_order(client, product_payload):
    product = client.post("/api/productos", json=product_payload).json()
    invalid = client.post("/api/pedidos/manuales", json={"producto_id": product["id"], "cantidad": "1.5"})
    assert invalid.status_code == 422
    order = client.post("/api/pedidos/manuales", json={"producto_id": product["id"], "cantidad": 3}).json()
    client.post(f"/api/alertas/{order['id']}/transicion", json={"estado": "APROBADO"})
    client.post(f"/api/alertas/{order['id']}/transicion", json={"estado": "PEDIDO", "cantidad_pedida": 3})
    conflict = client.post("/api/pedidos/manuales", json={"producto_id": product["id"], "cantidad": 2})
    assert conflict.status_code == 409


def test_bodeguero_is_forbidden_from_admin_endpoints(client):
    product = client.post("/api/productos", json={"codigo_qr": "PAL-008888", "nombre": "Producto",
        "categoria": "X", "ubicacion": "A", "unidad_medida": "unidad", "stock_minimo": 1, "stock_maximo": 5}).json()
    client.post("/api/auth/usuarios", json={"nombre": "operador", "rol": "BODEGUERO", "clave": "1234"})
    login = client.post("/api/auth/login", json={"usuario": "operador", "clave": "1234"}).json()
    client.headers["Authorization"] = f"Bearer {login['token']}"
    assert client.get("/api/alertas").status_code == 403
    assert client.get("/api/movimientos").status_code == 403
    assert client.get("/api/productos").status_code == 200
    assert client.post("/api/movimientos", json={"uuid": str(uuid4()), "producto_id": product["id"],
        "tipo": "AJUSTE", "cantidad_cambio": 1, "motivo": "Ajuste no permitido"}).status_code == 403
    assert client.post("/api/movimientos", json={"uuid": str(uuid4()), "producto_id": product["id"],
        "tipo": "ENTRADA", "cantidad_cambio": 1, "motivo": "Entrada permitida"}).status_code == 200


def test_admin_can_change_bounds_but_not_absolute_stock(client, product_payload):
    product = client.post("/api/productos", json=product_payload).json()
    changed = client.patch(f"/api/productos/{product['id']}", json={"stock_minimo": 3, "stock_maximo": 12,
        "stock_actual": 99})
    assert changed.status_code == 200
    assert changed.json()["stock_minimo"] == "3.000"
    assert changed.json()["stock_actual"] == "0.000"
    invalid = client.patch(f"/api/productos/{product['id']}", json={"stock_minimo": 12})
    assert invalid.status_code == 422


def test_dashboard_filters_and_discrepancy_resolution(client, product_payload):
    product = client.post("/api/productos", json=product_payload).json()
    client.post("/api/movimientos", json={"uuid": str(uuid4()), "producto_id": product["id"],
        "tipo": "SALIDA", "cantidad_cambio": -1, "motivo": "Salida offline"})
    dashboard = client.get("/api/dashboard/resumen?q=Guante").json()
    assert len(dashboard["criticos"]) == 1
    assert len(dashboard["discrepancias"]) == 1
    resolved = client.post(f"/api/discrepancias/{dashboard['discrepancias'][0]['id']}/resolver")
    assert resolved.json()["resuelta"] is True
