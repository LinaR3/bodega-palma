from pydantic import BaseModel, Field


class LoginIn(BaseModel):
    usuario: str = Field(min_length=1, max_length=100)
    clave: str = Field(min_length=4, max_length=128)
    dispositivo: str = Field(default="desconocido", min_length=1, max_length=120)


class LoginOut(BaseModel):
    token: str
    tipo: str = "Bearer"
    expira_en_dias: int = 90
    nombre: str
    rol: str


class UsuarioCrear(BaseModel):
    nombre: str = Field(min_length=1, max_length=100)
    rol: str = Field(pattern="^(ADMIN|BODEGUERO)$")
    clave: str = Field(min_length=4, max_length=128)
