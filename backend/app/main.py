import logging
import os
from logging.handlers import RotatingFileHandler

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from app.api.routes import router
from app.api.auth import router as auth_router
from app.core.config import settings
from app.core.database import engine

os.makedirs(os.path.dirname(settings.log_file) or ".", exist_ok=True)
root_logger = logging.getLogger()
root_logger.setLevel(logging.INFO)
formatter = logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s")
stream_handler = logging.StreamHandler()
stream_handler.setFormatter(formatter)
root_logger.addHandler(stream_handler)
try:
    file_handler = RotatingFileHandler(settings.log_file, maxBytes=10 * 1024 * 1024, backupCount=7, encoding="utf-8")
    file_handler.setFormatter(formatter)
    root_logger.addHandler(file_handler)
except OSError:
    logging.getLogger(__name__).exception("No se pudo abrir el archivo rotativo; se conservan logs en stdout")

app = FastAPI(title="Bodega Palma API", version="0.1.0")
app.add_middleware(CORSMiddleware, allow_origins=settings.allowed_origins,
                   allow_credentials=True, allow_methods=["GET", "POST"], allow_headers=["*"])
app.include_router(router)
app.include_router(auth_router)


@app.get("/health")
def health():
    with engine.connect() as connection:
        connection.execute(text("SELECT 1"))
    return {"status": "ok", "database": "ok"}
