from datetime import datetime, timezone

from sqlmodel import Field, SQLModel


class OcorrenciaAtividade(SQLModel, table=True):
    __tablename__ = "ocorrencia_atividades"

    id: int | None = Field(default=None, primary_key=True)
    ocorrencia_id: int = Field(
        foreign_key="ocorrencias.id",
        index=True,
        ondelete="CASCADE",
    )
    titulo: str = Field(max_length=160)
    descricao: str | None = Field(default=None, max_length=1000)
    concluida: bool = Field(default=False)
    created_by: int = Field(foreign_key="users.id")
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    concluida_em: datetime | None = Field(default=None)


class OcorrenciaEvidencia(SQLModel, table=True):
    __tablename__ = "ocorrencia_evidencias"

    id: int | None = Field(default=None, primary_key=True)
    ocorrencia_id: int = Field(
        foreign_key="ocorrencias.id",
        index=True,
        ondelete="CASCADE",
    )
    categoria: str = Field(max_length=20)
    nome_arquivo: str = Field(max_length=255)
    arquivo_salvo: str = Field(max_length=40, unique=True)
    tipo_mime: str = Field(max_length=100)
    tamanho: int = Field(ge=1)
    enviado_por: int = Field(foreign_key="users.id")
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )


class OcorrenciaHistorico(SQLModel, table=True):
    __tablename__ = "ocorrencia_historico"

    id: int | None = Field(default=None, primary_key=True)
    ocorrencia_id: int = Field(
        foreign_key="ocorrencias.id",
        index=True,
        ondelete="CASCADE",
    )
    ator_id: int | None = Field(default=None, foreign_key="users.id")
    acao: str = Field(max_length=40)
    descricao: str = Field(max_length=500)
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
