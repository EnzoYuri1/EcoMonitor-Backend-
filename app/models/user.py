from datetime import datetime, timezone
from typing import TYPE_CHECKING, Optional

from sqlmodel import Field, Relationship, SQLModel

if TYPE_CHECKING:
    from app.models.ocorrencia import Ocorrencia


class User(SQLModel, table=True):
    """Usuário responsável por registrar ocorrências ambientais."""

    __tablename__ = "users"

    id: int | None = Field(default=None, primary_key=True)
    nome: str = Field(max_length=120)
    email: str = Field(max_length=255, unique=True, index=True)
    senha_hash: str = Field(max_length=255)
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )

    ocorrencias: list["Ocorrencia"] = Relationship(back_populates="owner")
