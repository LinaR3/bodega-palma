import argparse
from getpass import getpass

from app.core.database import SessionLocal, engine
from app.core.security import hash_secret
from app.models.entities import Usuario
from sqlalchemy import inspect


def main():
    parser = argparse.ArgumentParser(description="Crear usuario inicial o administrativo")
    parser.add_argument("nombre")
    parser.add_argument("--rol", choices=["ADMIN", "BODEGUERO"], default="ADMIN")
    args = parser.parse_args()
    secret = getpass("Contraseña admin o PIN bodeguero: ")
    confirm = getpass("Repita la clave: ")
    if secret != confirm or len(secret) < (8 if args.rol == "ADMIN" else 4):
        raise SystemExit("Las claves no coinciden o no tienen la longitud mínima")
    if not inspect(engine).has_table("usuarios"):
        raise SystemExit("No hay esquema. Ejecute primero: alembic upgrade head")
    db = SessionLocal()
    try:
        if db.query(Usuario).filter_by(nombre=args.nombre).first():
            raise SystemExit("El usuario ya existe")
        db.add(Usuario(nombre=args.nombre, rol=args.rol, credencial_hash=hash_secret(secret)))
        db.commit()
    finally:
        db.close()


if __name__ == "__main__":
    main()
