from datetime import datetime
from typing import Annotated

from pydantic import (
    AfterValidator,
    BaseModel,
    BeforeValidator,
    ConfigDict,
    EmailStr,
    Field,
    field_validator,
)


def _normalizar_email(value: object) -> object:
    if isinstance(value, str):
        return value.strip().lower()
    return value


def _validar_senha_bcrypt(value: str) -> str:
    if len(value.encode("utf-8")) > 72:
        raise ValueError("A senha deve ter no máximo 72 bytes.")
    return value


EmailNormalizado = Annotated[EmailStr, BeforeValidator(_normalizar_email)]
Senha = Annotated[str, AfterValidator(_validar_senha_bcrypt)]


class UserBase(BaseModel):
    nome: str = Field(
        min_length=2,
        max_length=120,
        examples=["Maria Silva"],
        description="Nome completo do usuário.",
    )
    email: EmailNormalizado = Field(
        examples=["maria@example.com"],
        description="Email único do usuário.",
    )

    @field_validator("nome", mode="before")
    @classmethod
    def normalizar_nome(cls, value: object) -> object:
        if isinstance(value, str):
            return value.strip()
        return value


class UserCreate(UserBase):
    senha: Senha = Field(
        min_length=8,
        max_length=72,
        examples=["senhaSegura123"],
        description="Senha em texto puro; será armazenada apenas como hash.",
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "nome": "Maria Silva",
                "email": "maria@example.com",
                "senha": "senhaSegura123",
            }
        }
    )


class UserLogin(BaseModel):
    email: EmailNormalizado = Field(
        examples=["maria@example.com"],
        description="Email cadastrado.",
    )
    senha: Senha = Field(
        min_length=1,
        max_length=72,
        examples=["senhaSegura123"],
        description="Senha do usuário.",
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "email": "maria@example.com",
                "senha": "senhaSegura123",
            }
        }
    )


class UserRead(BaseModel):
    id: int
    nome: str
    email: EmailStr
    created_at: datetime

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "id": 1,
                "nome": "Maria Silva",
                "email": "maria@example.com",
                "created_at": "2026-10-30T14:00:00Z",
            }
        },
    )


class Token(BaseModel):
    access_token: str = Field(
        examples=["eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."],
        description="Token JWT de acesso.",
    )
    token_type: str = Field(
        default="bearer",
        examples=["bearer"],
        description="Tipo do token; deve ser enviado como Bearer.",
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
                "token_type": "bearer",
            }
        }
    )
