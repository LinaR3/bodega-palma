from datetime import datetime, timezone
from decimal import Decimal
import csv
import io
from fastapi import APIRouter, Depends, File, HTTPException, Response, UploadFile
from fastapi.responses import StreamingResponse
from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import require_roles
from app.models.entities import AlertaPedido, Discrepancia, EstadoAlerta, EventoAuditoria, MovimientoInventario, Producto, Usuario
from app.schemas.inventory import AlertaOut, AlertaTransicion, MovimientoCreate, MovimientoOut, ProductoCreate, ProductoOut, ProductoUpdate
from app.services.inventory import estado_stock, recalcular_sugerencia, registrar_movimiento
from app.services.files import MAX_IMPORT_BYTES, qr_labels_pdf, read_catalog, suggestions_pdf, suggestions_xlsx

router = APIRouter(prefix="/api")


def product_out(producto: Producto) -> ProductoOut:
    return ProductoOut.model_validate({**{k: getattr(producto, k) for k in (
        "id", "codigo_qr", "nombre", "categoria", "ubicacion", "unidad_medida",
        "stock_actual", "stock_minimo", "stock_maximo")},
        "estado": estado_stock(producto.stock_actual, producto.stock_minimo)})


@router.post("/productos", response_model=ProductoOut, status_code=201)
def crear_producto(data: ProductoCreate, db: Session = Depends(get_db), user: Usuario = Depends(require_roles("ADMIN"))):
    if db.scalar(select(Producto).where(Producto.codigo_qr == data.codigo_qr)):
        raise HTTPException(status_code=409, detail="codigo_qr ya existe")
    producto = Producto(**data.model_dump(), stock_actual=0)
    db.add(producto)
    db.flush()
    db.add(EventoAuditoria(usuario_id=user.id, usuario_nombre=user.nombre, accion="CREAR_PRODUCTO",
        entidad="producto", entidad_id=str(producto.id), dispositivo="web", detalle="{}"))
    db.commit()
    db.refresh(producto)
    return product_out(producto)


@router.patch("/productos/{producto_id}", response_model=ProductoOut)
def actualizar_producto(producto_id: int, data: ProductoUpdate, db: Session = Depends(get_db),
                        user: Usuario = Depends(require_roles("ADMIN"))):
    producto = db.get(Producto, producto_id)
    if not producto:
        raise HTTPException(404, "Producto no encontrado")
    changes = data.model_dump(exclude_unset=True)
    if "activo" in changes and changes["activo"] is None:
        raise HTTPException(422, "activo no puede ser nulo")
    merged = {key: getattr(producto, key) for key in (
        "codigo_qr", "nombre", "categoria", "ubicacion", "unidad_medida", "stock_minimo", "stock_maximo")}
    merged.update({k: v for k, v in changes.items() if k != "activo"})
    try:
        validated = ProductoCreate.model_validate(merged)
    except Exception as exc:
        raise HTTPException(422, str(exc))
    if validated.codigo_qr != producto.codigo_qr and db.scalar(select(Producto.id).where(
            Producto.codigo_qr == validated.codigo_qr, Producto.id != producto.id)):
        raise HTTPException(409, "codigo_qr ya existe")
    for key, value in validated.model_dump().items():
        setattr(producto, key, value)
    if "activo" in changes:
        producto.activo = changes["activo"]
    db.flush()
    recalcular_sugerencia(db, producto)
    db.add(EventoAuditoria(usuario_id=user.id, usuario_nombre=user.nombre, accion="ACTUALIZAR_PRODUCTO",
        entidad="producto", entidad_id=str(producto.id), dispositivo="web", detalle="{" + ",".join(f'\"{key}\":true' for key in changes) + "}"))
    db.commit(); db.refresh(producto)
    return product_out(producto)


@router.post("/catalogo/importar", dependencies=[Depends(require_roles("ADMIN"))])
async def importar_catalogo(file: UploadFile = File(...), db: Session = Depends(get_db),
                           user: Usuario = Depends(require_roles("ADMIN"))):
    content = await file.read(MAX_IMPORT_BYTES + 1)
    try:
        rows, errors = read_catalog(content, file.filename or "")
    except (ValueError, UnicodeDecodeError) as exc:
        raise HTTPException(422, str(exc))
    seen = set()
    inserted = 0
    for line, item in rows:
        if item.codigo_qr in seen or db.scalar(select(Producto.id).where(Producto.codigo_qr == item.codigo_qr)):
            errors.append({"fila": line, "error": f"codigo_qr duplicado: {item.codigo_qr}"})
            continue
        seen.add(item.codigo_qr)
        db.add(Producto(**item.model_dump(), stock_actual=Decimal(0)))
        inserted += 1
    db.add(EventoAuditoria(usuario_id=user.id, usuario_nombre=user.nombre, accion="IMPORTAR_CATALOGO",
        entidad="producto", entidad_id=None, dispositivo="web", detalle=f"{{\"insertados\":{inserted}}}"))
    db.commit()
    report = io.StringIO(); writer = csv.writer(report); writer.writerow(["fila", "error"])
    writer.writerows([[e["fila"], e["error"]] for e in errors])
    return {"insertados": inserted, "errores": errors,
            "reporte_csv": report.getvalue() if errors else None}


@router.get("/catalogo/plantilla.xlsx", dependencies=[Depends(require_roles("ADMIN"))])
def plantilla_catalogo():
    from openpyxl import Workbook
    wb = Workbook(); ws = wb.active; ws.title = "Catalogo"
    ws.append(["codigo_qr", "nombre", "categoria", "ubicacion", "unidad_medida", "stock_minimo", "stock_maximo"])
    ws.append(["PAL-000123", "Ejemplo botella", "Insumos", "Estante A", "botella", 2, 10])
    output = io.BytesIO(); wb.save(output); output.seek(0)
    return StreamingResponse(output, media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                             headers={"Content-Disposition": "attachment; filename=plantilla-catalogo.xlsx"})


@router.get("/productos", response_model=list[ProductoOut], dependencies=[Depends(require_roles("ADMIN", "BODEGUERO"))])
def listar_productos(q: str | None = None, db: Session = Depends(get_db)):
    stmt = select(Producto).where(Producto.activo.is_(True)).order_by(Producto.nombre).limit(500)
    if q:
        if len(q) > 100:
            raise HTTPException(status_code=422, detail="Búsqueda demasiado larga")
        stmt = stmt.where((Producto.nombre.ilike(f"%{q}%")) | (Producto.codigo_qr.ilike(f"%{q}%")))
    return [product_out(p) for p in db.scalars(stmt).all()]


@router.post("/movimientos", response_model=MovimientoOut)
def crear_movimiento(data: MovimientoCreate, response: Response, db: Session = Depends(get_db),
                     user: Usuario = Depends(require_roles("ADMIN", "BODEGUERO"))):
    if user.rol == "BODEGUERO" and data.tipo not in {"ENTRADA", "SALIDA"}:
        raise HTTPException(403, "BODEGUERO solo puede registrar entradas y salidas")
    data = data.model_copy(update={"usuario_id": user.id, "usuario_nombre": user.nombre})
    movement, repeated = registrar_movimiento(db, data)
    response.headers["Idempotent-Replay"] = "true" if repeated else "false"
    return MovimientoOut.model_validate({**{k: getattr(movement, k) for k in (
        "id", "uuid", "producto_id", "tipo", "cantidad_cambio", "motivo", "destino_area",
        "usuario_id", "usuario_nombre", "dispositivo", "fecha_cliente", "fecha_servidor",
        "stock_resultante", "movimiento_referenciado_id")}, "repetido": repeated})


@router.get("/movimientos", response_model=list[MovimientoOut], dependencies=[Depends(require_roles("ADMIN"))])
def listar_movimientos(limit: int = 100, db: Session = Depends(get_db)):
    if not 1 <= limit <= 500:
        raise HTTPException(status_code=422, detail="limit debe estar entre 1 y 500")
    rows = db.scalars(select(MovimientoInventario)
                      .order_by(MovimientoInventario.fecha_servidor.desc(), MovimientoInventario.id.desc()).limit(limit)).all()
    return [MovimientoOut.model_validate(r) for r in rows]


@router.get("/alertas", response_model=list[AlertaOut], dependencies=[Depends(require_roles("ADMIN"))])
def listar_alertas(db: Session = Depends(get_db)):
    return db.scalars(select(AlertaPedido).order_by(AlertaPedido.id.desc()).limit(500)).all()


@router.get("/exportar/pedidos.xlsx", dependencies=[Depends(require_roles("ADMIN"))])
def exportar_pedidos_xlsx(db: Session = Depends(get_db)):
    alerts = db.scalars(select(AlertaPedido).where(AlertaPedido.estado == EstadoAlerta.SUGERIDO).order_by(AlertaPedido.id)).all()
    products = {p.id: p for p in db.scalars(select(Producto).where(Producto.id.in_([a.producto_id for a in alerts]))).all()} if alerts else {}
    return StreamingResponse(io.BytesIO(suggestions_xlsx(alerts, products)), media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                             headers={"Content-Disposition": "attachment; filename=pedidos-sugeridos.xlsx"})


@router.get("/exportar/pedidos.pdf", dependencies=[Depends(require_roles("ADMIN"))])
def exportar_pedidos_pdf(db: Session = Depends(get_db)):
    alerts = db.scalars(select(AlertaPedido).where(AlertaPedido.estado == EstadoAlerta.SUGERIDO).order_by(AlertaPedido.id)).all()
    products = {p.id: p for p in db.scalars(select(Producto).where(Producto.id.in_([a.producto_id for a in alerts]))).all()} if alerts else {}
    return StreamingResponse(io.BytesIO(suggestions_pdf(alerts, products)), media_type="application/pdf",
                             headers={"Content-Disposition": "attachment; filename=pedidos-sugeridos.pdf"})


@router.get("/etiquetas.pdf", dependencies=[Depends(require_roles("ADMIN"))])
def etiquetas_pdf(db: Session = Depends(get_db)):
    products = db.scalars(select(Producto).where(Producto.activo.is_(True)).order_by(Producto.codigo_qr).limit(500)).all()
    return StreamingResponse(io.BytesIO(qr_labels_pdf(products)), media_type="application/pdf",
                             headers={"Content-Disposition": "attachment; filename=etiquetas-qr.pdf"})


@router.get("/auditoria", dependencies=[Depends(require_roles("ADMIN"))])
def listar_auditoria(limit: int = 100, db: Session = Depends(get_db)):
    if not 1 <= limit <= 500:
        raise HTTPException(422, "limit debe estar entre 1 y 500")
    return db.scalars(select(EventoAuditoria).order_by(EventoAuditoria.fecha_servidor.desc()).limit(limit)).all()


@router.get("/dashboard/resumen", dependencies=[Depends(require_roles("ADMIN"))])
def resumen_dashboard(q: str | None = None, categoria: str | None = None,
                      desde: datetime | None = None, hasta: datetime | None = None,
                      db: Session = Depends(get_db)):
    products = db.scalars(select(Producto).where(Producto.activo.is_(True)).order_by(Producto.nombre).limit(1000)).all()
    if q:
        if len(q) > 100: raise HTTPException(422, "Búsqueda demasiado larga")
        products = [p for p in products if q.casefold() in p.nombre.casefold() or q.casefold() in p.codigo_qr.casefold()]
    if categoria:
        products = [p for p in products if p.categoria.casefold() == categoria.casefold()]
    product_ids = [p.id for p in products]
    states = {"CRITICO": 0, "PRECAUCION": 0, "OPTIMO": 0}
    for p in products:
        states[estado_stock(p.stock_actual, p.stock_minimo)] += 1
    alerts = db.scalars(select(AlertaPedido).where(
        AlertaPedido.producto_id.in_(product_ids),
        AlertaPedido.estado.in_([EstadoAlerta.SUGERIDO, EstadoAlerta.APROBADO, EstadoAlerta.PEDIDO])
    ).order_by(AlertaPedido.actualizada_en.desc()).limit(200)).all() if product_ids else []
    discrepancies = db.execute(select(Discrepancia, Producto.nombre, Producto.codigo_qr)
        .join(Producto, Producto.id == Discrepancia.producto_id)
        .where(Discrepancia.resuelta.is_(False)).order_by(Discrepancia.creada_en.desc()).limit(100)).all()
    movement_query = select(MovimientoInventario, Producto.nombre, Producto.codigo_qr).join(Producto)
    if product_ids:
        movement_query = movement_query.where(MovimientoInventario.producto_id.in_(product_ids))
    if desde: movement_query = movement_query.where(MovimientoInventario.fecha_servidor >= desde)
    if hasta: movement_query = movement_query.where(MovimientoInventario.fecha_servidor <= hasta)
    movements = db.execute(movement_query.order_by(MovimientoInventario.fecha_servidor.desc(), MovimientoInventario.id.desc()).limit(100)).all()
    categories = sorted(set(db.scalars(select(Producto.categoria).distinct()).all()))
    return {
        "actualizado_en": datetime.now(timezone.utc), "conteos": states,
        "productos": [product_out(p).model_dump(mode="json") for p in products],
        "criticos": [product_out(p).model_dump(mode="json") for p in products if estado_stock(p.stock_actual, p.stock_minimo) == "CRITICO"],
        "alertas": [{"id": a.id, "producto_id": a.producto_id, "producto": next((p.nombre for p in products if p.id == a.producto_id), ""),
                     "estado": a.estado.value, "cantidad_sugerida": str(a.cantidad_sugerida),
                     "cantidad_pedida": str(a.cantidad_pedida), "cantidad_recibida": str(a.cantidad_recibida)} for a in alerts],
        "discrepancias": [{"id": d.id, "producto": name, "codigo_qr": code, "movimiento_id": d.movimiento_id,
                           "tipo": d.tipo, "detalle": d.detalle, "creada_en": d.creada_en.isoformat()} for d, name, code in discrepancies],
        "movimientos": [{"id": m.id, "producto": name, "codigo_qr": code, "tipo": m.tipo.value,
                         "cantidad_cambio": str(m.cantidad_cambio), "motivo": m.motivo,
                         "destino_area": m.destino_area, "usuario": m.usuario_nombre,
                         "dispositivo": m.dispositivo, "fecha_servidor": m.fecha_servidor.isoformat(),
                         "stock_resultante": str(m.stock_resultante)} for m, name, code in movements],
        "categorias": categories,
    }


@router.post("/discrepancias/{discrepancia_id}/resolver")
def resolver_discrepancia(discrepancia_id: int, db: Session = Depends(get_db),
                          user: Usuario = Depends(require_roles("ADMIN"))):
    discrepancy = db.get(Discrepancia, discrepancia_id)
    if not discrepancy:
        raise HTTPException(404, "Discrepancia no encontrada")
    discrepancy.resuelta = True
    db.add(EventoAuditoria(usuario_id=user.id, usuario_nombre=user.nombre, accion="RESOLVER_DISCREPANCIA",
        entidad="discrepancia", entidad_id=str(discrepancy.id), dispositivo="web", detalle="{}"))
    db.commit()
    return {"id": discrepancy.id, "resuelta": discrepancy.resuelta}


@router.post("/alertas/{alerta_id}/transicion", response_model=AlertaOut)
def transicionar_alerta(alerta_id: int, data: AlertaTransicion, db: Session = Depends(get_db),
                        user: Usuario = Depends(require_roles("ADMIN"))):
    alerta = db.get(AlertaPedido, alerta_id)
    if not alerta:
        raise HTTPException(status_code=404, detail="Alerta no encontrada")
    if data.estado == "RECIBIDO" and data.uuid_movimiento:
        prior = db.scalar(select(MovimientoInventario).where(MovimientoInventario.uuid == data.uuid_movimiento))
        if prior:
            # A retried receipt must not add the same quantity twice.
            if prior.producto_id != alerta.producto_id or prior.motivo != f"Recepción de pedido {alerta.id}":
                raise HTTPException(409, "uuid_movimiento ya está asociado a otra operación")
            return alerta
    anterior = alerta.estado
    nuevo = EstadoAlerta(data.estado)
    permitidos = {
        EstadoAlerta.SUGERIDO: {EstadoAlerta.APROBADO, EstadoAlerta.CANCELADO},
        EstadoAlerta.APROBADO: {EstadoAlerta.PEDIDO, EstadoAlerta.CANCELADO},
        EstadoAlerta.PEDIDO: {EstadoAlerta.RECIBIDO, EstadoAlerta.CANCELADO},
    }
    if nuevo not in permitidos.get(anterior, set()):
        raise HTTPException(status_code=409, detail=f"Transición no permitida: {anterior} -> {nuevo}")
    producto = db.get(Producto, alerta.producto_id)
    if nuevo == EstadoAlerta.PEDIDO:
        qty = data.cantidad_pedida or alerta.cantidad_sugerida
        if qty <= 0 or qty != qty.to_integral_value():
            raise HTTPException(status_code=422, detail="La cantidad pedida debe ser un entero positivo")
        alerta.cantidad_pedida = qty
        alerta.estado = nuevo
    elif nuevo == EstadoAlerta.RECIBIDO:
        if not data.uuid_movimiento:
            raise HTTPException(status_code=422, detail="uuid_movimiento es obligatorio al recibir")
        qty = data.cantidad_recibida or (alerta.cantidad_pedida - alerta.cantidad_recibida)
        pendiente = alerta.cantidad_pedida - alerta.cantidad_recibida
        if qty <= 0 or qty != qty.to_integral_value() or qty > pendiente:
            raise HTTPException(status_code=422, detail="Cantidad recibida inválida")
        # Receipt and stock update are committed together in the same transaction.
        from app.models.entities import TipoMovimiento
        new_stock = db.execute(update(Producto).where(Producto.id == producto.id).values(
            stock_actual=Producto.stock_actual + qty).returning(Producto.stock_actual)).scalar_one()
        movement = MovimientoInventario(
            uuid=data.uuid_movimiento, producto_id=alerta.producto_id, tipo=TipoMovimiento.ENTRADA,
            cantidad_cambio=qty, motivo=f"Recepción de pedido {alerta.id}",
            usuario_nombre=data.usuario_nombre, dispositivo=data.dispositivo,
            usuario_id=user.id, fecha_servidor=datetime.now(timezone.utc), stock_resultante=new_stock,
        )
        db.add(movement)
        db.flush()
        if new_stock < 0:
            db.add(Discrepancia(producto_id=producto.id, movimiento_id=movement.id,
                detalle=f"Stock negativo luego de la recepción {movement.id}: {new_stock}"))
        alerta.cantidad_recibida += qty
        alerta.estado = EstadoAlerta.RECIBIDO if alerta.cantidad_recibida >= alerta.cantidad_pedida else EstadoAlerta.PEDIDO
    else:
        alerta.estado = nuevo
    if not (nuevo == EstadoAlerta.CANCELADO and anterior == EstadoAlerta.SUGERIDO):
        recalcular_sugerencia(db, producto)
    db.add(EventoAuditoria(usuario_id=user.id, usuario_nombre=user.nombre,
        accion=f"ALERTA_{nuevo.value}", entidad="alerta_pedido", entidad_id=str(alerta.id),
        dispositivo=data.dispositivo, detalle="{}"))
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        prior = db.scalar(select(MovimientoInventario).where(MovimientoInventario.uuid == data.uuid_movimiento)) if data.uuid_movimiento else None
        if prior and prior.producto_id == alerta.producto_id and prior.motivo == f"Recepción de pedido {alerta.id}":
            return db.get(AlertaPedido, alerta_id)
        raise
    db.refresh(alerta)
    return alerta
