import hashlib
import secrets
from datetime import datetime, timedelta, timezone

from argon2 import PasswordHasher
from argon2.exceptions import VerificationError
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.entities import Sesion, Usuario

hasher = PasswordHasher()
bearer = HTTPBearer(auto_error=False)
SESSION_DAYS = 90


def hash_secret(value: str) -> str:
    return hasher.hash(value)


def verify_secret(encoded: str, value: str) -> bool:
    try:
        return hasher.verify(encoded, value)
    except VerificationError:
        return False


def token_digest(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def issue_session(db: Session, user: Usuario, device: str) -> str:
    raw = secrets.token_urlsafe(40)
    db.add(Sesion(usuario_id=user.id, token_hash=token_digest(raw), dispositivo=device,
                  expira_en=datetime.now(timezone.utc) + timedelta(days=SESSION_DAYS)))
    return raw


def current_user(credentials: HTTPAuthorizationCredentials | None = Depends(bearer),
                 db: Session = Depends(get_db)) -> Usuario:
    if not credentials:
        raise HTTPException(401, "Autenticación requerida", headers={"WWW-Authenticate": "Bearer"})
    session = db.scalar(select(Sesion).where(Sesion.token_hash == token_digest(credentials.credentials)))
    now = datetime.now(timezone.utc)
    if not session or session.revocada or session.expira_en <= now:
        raise HTTPException(401, "Sesión inválida o vencida", headers={"WWW-Authenticate": "Bearer"})
    user = db.get(Usuario, session.usuario_id)
    if not user or not user.activo:
        raise HTTPException(401, "Usuario inactivo")
    return user


def require_roles(*roles: str):
    def dependency(user: Usuario = Depends(current_user)):
        if user.rol not in roles:
            raise HTTPException(403, "No tiene permisos para esta operación")
        return user
    return dependency
