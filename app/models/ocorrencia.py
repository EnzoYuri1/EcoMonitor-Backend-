from datetime import date, datetime, timezone
from enum import Enum

from typing import TYPE_CHECKING, Optional

from sqlalchemy import Column, Enum as SAEnum
from sqlmodel import Field, Relationship, SQLModel

if TYPE_CHECKING:
    from app.models.user import User


class TipoOcorrencia(str, Enum):
    """Tipos de ocorrência ambiental suportados pelo sistema."""

    QUEIMADA = "queimada"
    DESMATAMENTO = "desmatamento"


class Ocorrencia(SQLModel, table=True):
    """Registro de uma ocorrência ambiental."""

    __tablename__ = "ocorrencias"

    id: int | None = Field(default=None, primary_key=True)
    tipo: TipoOcorrencia = Field(
        sa_column=Column(
            SAEnum(
                TipoOcorrencia,
                native_enum=False,
                create_constraint=True,
                values_callable=lambda enum_cls: [
                    item.value for item in enum_cls
                ],
                name="ck_ocorrencias_tipo",
            ),
            nullable=False,
            index=True,
        )
    )
    municipio: str = Field(max_length=120, index=True)
    estado: str = Field(max_length=2)
    descricao: str
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)
    data_ocorrencia: date = Field(index=True)
    created_by: int = Field(foreign_key="users.id", index=True)
    status: str = Field(default="registrada", max_length=24, index=True)
    prioridade: str = Field(default="media", max_length=12)
    prazo: date | None = Field(default=None)
    responsavel_id: int | None = Field(
        default=None,
        foreign_key="users.id",
        index=True,
    )
    resolucao: str | None = Field(default=None, max_length=4000)
    observacao_validacao: str | None = Field(default=None, max_length=2000)
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )

    owner: Optional["User"] = Relationship(
        back_populates="ocorrencias",
        sa_relationship_kwargs={
            "foreign_keys": "Ocorrencia.created_by",
        },
    )
