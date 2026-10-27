from collections import defaultdict, deque
from datetime import datetime, timezone
from time import monotonic

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import current_user, hash_secret, issue_session, require_roles, token_digest, verify_secret
from app.models.entities import EventoAuditoria, Sesion, Usuario
from app.schemas.auth import LoginIn, LoginOut, UsuarioCrear

router = APIRouter(prefix="/api/auth", tags=["autenticación"])
failures: dict[str, deque[float]] = defaultdict(deque)


@router.post("/login", response_model=LoginOut)
def login(data: LoginIn, request: Request, db: Session = Depends(get_db)):
    key = request.client.host if request.client else "unknown"
    now = monotonic()
    recent = failures[key]
    while recent and now - recent[0] > 60:
        recent.popleft()
    if len(recent) >= 8:
        raise HTTPException(429, "Demasiados intentos. Espere un minuto.")
    user = db.scalar(select(Usuario).where(Usuario.nombre == data.usuario, Usuario.activo.is_(True)))
    if not user or not user.credencial_hash or not verify_secret(user.credencial_hash, data.clave):
        recent.append(now)
        raise HTTPException(401, "Usuario o clave incorrectos")
    failures.pop(key, None)
    token = issue_session(db, user, data.dispositivo)
    db.add(EventoAuditoria(usuario_id=user.id, usuario_nombre=user.nombre, accion="INICIO_SESION",
        entidad="sesion", dispositivo=data.dispositivo, detalle="{}"))
    db.commit()
    return LoginOut(token=token, nombre=user.nombre, rol=user.rol)


@router.post("/logout", status_code=204)
def logout(request: Request, user: Usuario = Depends(current_user), db: Session = Depends(get_db)):
    # Revoke the bearer session used by this request.
    auth = request.headers.get("authorization", "") if request else ""
    raw = auth.removeprefix("Bearer ")
    session = db.scalar(select(Sesion).where(Sesion.token_hash == token_digest(raw)))
    if session:
        session.revocada = True
        db.add(EventoAuditoria(usuario_id=user.id, usuario_nombre=user.nombre, accion="CERRAR_SESION",
            entidad="sesion", entidad_id=str(session.id), dispositivo=session.dispositivo, detalle="{}"))
        db.commit()


@router.post("/usuarios", status_code=201)
def crear_usuario(data: UsuarioCrear, admin: Usuario = Depends(require_roles("ADMIN")), db: Session = Depends(get_db)):
    if data.rol == "ADMIN" and len(data.clave) < 8:
        raise HTTPException(422, "La contraseña de ADMIN debe tener al menos 8 caracteres")
    if db.scalar(select(Usuario.id).where(Usuario.nombre == data.nombre)):
        raise HTTPException(409, "El usuario ya existe")
    user = Usuario(nombre=data.nombre, rol=data.rol, credencial_hash=hash_secret(data.clave))
    db.add(user); db.flush()
    db.add(EventoAuditoria(usuario_id=admin.id, usuario_nombre=admin.nombre, accion="CREAR_USUARIO",
        entidad="usuario", entidad_id=str(user.id), dispositivo="web", detalle=f"{{\"rol\":\"{user.rol}\"}}"))
    db.commit()
    return {"id": user.id, "nombre": user.nombre, "rol": user.rol}


@router.post("/usuarios/{user_id}/revocar-sesiones", status_code=204)
def revocar_sesiones(user_id: int, admin: Usuario = Depends(require_roles("ADMIN")), db: Session = Depends(get_db)):
    user = db.get(Usuario, user_id)
    if not user:
        raise HTTPException(404, "Usuario no encontrado")
    sessions = db.scalars(select(Sesion).where(Sesion.usuario_id == user_id, Sesion.revocada.is_(False))).all()
    for session in sessions:
        session.revocada = True
    db.add(EventoAuditoria(usuario_id=admin.id, usuario_nombre=admin.nombre, accion="REVOCAR_SESIONES",
        entidad="usuario", entidad_id=str(user_id), dispositivo="web", detalle=f"{{\"sesiones\":{len(sessions)}}}"))
    db.commit()
