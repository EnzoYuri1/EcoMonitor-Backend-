from datetime import date, datetime
from typing import Annotated, Literal

from pydantic import (
    AfterValidator,
    BaseModel,
    BeforeValidator,
    ConfigDict,
    Field,
    StringConstraints,
    model_validator,
)

from app.models import TipoOcorrencia


def _validar_data_nao_futura(value: date) -> date:
    if value > date.today():
        raise ValueError("A data da ocorrência não pode ser futura.")
    return value


def _normalizar_uf(value: object) -> object:
    if isinstance(value, str):
        return value.strip().upper()
    return value


DataOcorrencia = Annotated[date, AfterValidator(_validar_data_nao_futura)]
Uf = Annotated[
    Literal[
        "AC",
        "AL",
        "AP",
        "AM",
        "BA",
        "CE",
        "DF",
        "ES",
        "GO",
        "MA",
        "MT",
        "MS",
        "MG",
        "PA",
        "PB",
        "PR",
        "PE",
        "PI",
        "RJ",
        "RN",
        "RS",
        "RO",
        "RR",
        "SC",
        "SP",
        "SE",
        "TO",
    ],
    BeforeValidator(_normalizar_uf),
]
Municipio = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=2, max_length=120),
]
Descricao = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=5, max_length=2000),
]


class OcorrenciaCreate(BaseModel):
    tipo: TipoOcorrencia = Field(description="Tipo da ocorrência ambiental.")
    municipio: Municipio = Field(
        examples=["Sinop"],
        description="Município da ocorrência.",
    )
    estado: Uf = Field(
        examples=["MT"],
        description="UF do estado da ocorrência.",
    )
    descricao: Descricao = Field(
        examples=["Foco de queimada identificado próximo à rodovia."],
        description="Descrição detalhada da ocorrência.",
    )
    latitude: float | None = Field(
        default=None,
        ge=-90,
        le=90,
        examples=[-11.8642],
        description="Latitude opcional entre -90 e 90.",
    )
    longitude: float | None = Field(
        default=None,
        ge=-180,
        le=180,
        examples=[-55.5025],
        description="Longitude opcional entre -180 e 180.",
    )
    data_ocorrencia: DataOcorrencia = Field(
        examples=["2026-10-01"],
        description="Data da ocorrência; não pode ser futura.",
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "tipo": "queimada",
                "municipio": "Sinop",
                "estado": "MT",
                "descricao": "Foco de queimada próximo à rodovia.",
                "latitude": -11.8642,
                "longitude": -55.5025,
                "data_ocorrencia": "2026-10-01",
            }
        }
    )


class OcorrenciaUpdate(BaseModel):
    tipo: TipoOcorrencia | None = None
    municipio: Municipio | None = None
    estado: Uf | None = None
    descricao: Descricao | None = None
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)
    data_ocorrencia: DataOcorrencia | None = None

    @model_validator(mode="after")
    def validar_atualizacao(self) -> "OcorrenciaUpdate":
        if not self.model_fields_set:
            raise ValueError("Informe ao menos um campo para atualizar.")

        campos_obrigatorios = (
            "tipo",
            "municipio",
            "estado",
            "descricao",
            "data_ocorrencia",
        )
        for campo in campos_obrigatorios:
            if campo in self.model_fields_set and getattr(self, campo) is None:
                raise ValueError(f"O campo '{campo}' não pode ser nulo.")
        return self


class OcorrenciaRead(BaseModel):
    id: int
    tipo: TipoOcorrencia
    municipio: str
    estado: str
    descricao: str
    latitude: float | None
    longitude: float | None
    data_ocorrencia: date
    created_by: int
    status: Literal[
        "registrada",
        "em_execucao",
        "em_validacao",
        "concluida",
    ]
    prioridade: Literal["baixa", "media", "alta", "critica"]
    prazo: date | None
    responsavel_id: int | None
    resolucao: str | None
    observacao_validacao: str | None
    created_at: datetime

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "id": 1,
                "tipo": "queimada",
                "municipio": "Sinop",
                "estado": "MT",
                "descricao": "Foco de queimada próximo à rodovia.",
                "latitude": -11.8642,
                "longitude": -55.5025,
                "data_ocorrencia": "2026-10-01",
                "created_by": 1,
                "status": "registrada",
                "prioridade": "media",
                "prazo": None,
                "responsavel_id": None,
                "resolucao": None,
                "observacao_validacao": None,
                "created_at": "2026-10-30T14:00:00Z",
            }
        },
    )


class AtividadeRead(BaseModel):
    id: int
    titulo: str
    descricao: str | None
    concluida: bool
    created_by: int
    created_at: datetime
    concluida_em: datetime | None


class EvidenciaRead(BaseModel):
    id: int
    categoria: Literal["inicial", "execucao", "conclusao"]
    nome_arquivo: str
    tipo_mime: str
    tamanho: int
    enviado_por: int
    created_at: datetime


class HistoricoRead(BaseModel):
    id: int
    ator_id: int | None
    acao: str
    descricao: str
    created_at: datetime


class OcorrenciaDetalhe(OcorrenciaRead):
    atividades: list[AtividadeRead]
    evidencias: list[EvidenciaRead]
    historico: list[HistoricoRead]


class TriagemInput(BaseModel):
    prioridade: Literal["baixa", "media", "alta", "critica"]
    prazo: date
    responsavel_id: int


class AtividadeCreate(BaseModel):
    titulo: Annotated[
        str,
        StringConstraints(strip_whitespace=True, min_length=3, max_length=160),
    ]
    descricao: Annotated[
        str | None,
        StringConstraints(strip_whitespace=True, max_length=1000),
    ] = None


class AtividadeUpdate(BaseModel):
    concluida: bool


class SolicitacaoConclusao(BaseModel):
    resolucao: Annotated[
        str,
        StringConstraints(strip_whitespace=True, min_length=10, max_length=4000),
    ]


class ValidacaoConclusao(BaseModel):
    aprovado: bool
    comentario: Annotated[
        str | None,
        StringConstraints(strip_whitespace=True, max_length=2000),
    ] = None
