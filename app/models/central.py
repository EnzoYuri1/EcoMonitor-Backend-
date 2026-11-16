from datetime import date, datetime, timezone
from enum import Enum

from sqlmodel import Field, SQLModel


class CategoriaNoticia(str, Enum):
    """Categorias temáticas para notícias ambientais."""

    QUEIMADAS = "queimadas"
    DESMATAMENTO = "desmatamento"
    AMAZONIA = "amazonia"
    PARA = "para"
    CLIMA = "clima"
    FISCALIZACAO = "fiscalizacao"
    PRESERVACAO = "preservacao"


class TipoMetricaAmbiental(str, Enum):
    """Tipos distintos de dados oficiais ambientais (não equivalentes)."""

    FOCO_DE_CALOR = "foco_de_calor"
    ALERTA_DESMATAMENTO = "alerta_desmatamento"
    DESMATAMENTO_CONSOLIDADO = "desmatamento_consolidado"


class Noticia(SQLModel, table=True):
    """Notícia ambiental coletada de RSS ou API jornalística."""

    __tablename__ = "central_noticias"

    id: int | None = Field(default=None, primary_key=True)
    titulo: str = Field(max_length=500, index=True)
    descricao: str = Field(default="", max_length=2000)
    imagem_url: str | None = Field(default=None, max_length=1000)
    veiculo: str = Field(max_length=160, index=True)
    origem_integracao: str = Field(max_length=80, index=True)
    url_original: str = Field(max_length=1000)
    url_normalizada: str = Field(max_length=1000, unique=True, index=True)
    data_publicacao: datetime | None = Field(default=None, index=True)
    categoria: str = Field(default="preservacao", max_length=40, index=True)
    idioma: str = Field(default="pt", max_length=10)
    coletado_em: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        index=True,
    )


class ArtigoCientifico(SQLModel, table=True):
    """Publicação científica ou acadêmica coletada de bases abertas."""

    __tablename__ = "central_artigos"

    id: int | None = Field(default=None, primary_key=True)
    titulo: str = Field(max_length=800, index=True)
    autores: str = Field(default="", max_length=1500)
    instituicao_ou_periodico: str = Field(default="", max_length=400)
    ano_publicacao: int | None = Field(default=None, index=True)
    resumo: str = Field(default="", max_length=4000)
    palavras_chave: str = Field(default="", max_length=800)
    doi: str | None = Field(default=None, max_length=255, index=True)
    identificador_unico: str = Field(max_length=320, unique=True, index=True)
    url_original: str = Field(max_length=1000)
    base_origem: str = Field(max_length=80, index=True)
    categoria: str = Field(default="amazonia", max_length=40, index=True)
    citacoes: int = Field(default=0)
    pesquisa_brasileira: bool = Field(default=False, index=True)
    coletado_em: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        index=True,
    )


class DadoAmbientalOficial(SQLModel, table=True):
    """Indicador ou registro oficial de instituições ambientais (INPE, NASA FIRMS)."""

    __tablename__ = "central_dados_ambientais"

    id: int | None = Field(default=None, primary_key=True)
    tipo_metrica: str = Field(max_length=40, index=True)
    fonte: str = Field(max_length=120, index=True)
    instituicao: str = Field(max_length=160)
    identificador_original: str = Field(
        max_length=255, unique=True, index=True
    )
    estado: str = Field(max_length=2, index=True)
    municipio: str | None = Field(default=None, max_length=120, index=True)
    bioma: str = Field(default="Amazônia", max_length=80, index=True)
    amazonia_legal: bool = Field(default=True, index=True)
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)
    data_referencia: date = Field(index=True)
    periodo_rotulo: str = Field(default="", max_length=80)
    valor: float = Field(default=0.0)
    unidade: str = Field(default="focos", max_length=40)
    satelite_ou_metodo: str | None = Field(default=None, max_length=120)
    nivel_confianca: str = Field(default="oficial", max_length=40)
    url_fonte: str = Field(default="", max_length=1000)
    observacao: str | None = Field(default=None, max_length=1000)
    coletado_em: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        index=True,
    )


class IntegracaoStatus(SQLModel, table=True):
    """Estado de execução e saúde de cada integração externa."""

    __tablename__ = "central_integracoes_status"

    id: int | None = Field(default=None, primary_key=True)
    chave: str = Field(max_length=80, unique=True, index=True)
    nome: str = Field(max_length=160)
    categoria: str = Field(max_length=40, index=True)
    status: str = Field(default="nao_executada", max_length=40)
    configurada: bool = Field(default=True)
    ultima_tentativa: datetime | None = Field(default=None)
    ultima_atualizacao: datetime | None = Field(default=None)
    total_itens_ultima_coleta: int = Field(default=0)
    mensagem: str = Field(default="Aguardando primeira coleta.", max_length=1000)
    url_documentacao: str = Field(default="", max_length=500)


class IntegracaoLog(SQLModel, table=True):
    """Histórico auditável de execuções e falhas das integrações."""

    __tablename__ = "central_integracoes_logs"

    id: int | None = Field(default=None, primary_key=True)
    chave_integracao: str = Field(max_length=80, index=True)
    status: str = Field(max_length=40)
    itens_processados: int = Field(default=0)
    duracao_ms: int = Field(default=0)
    detalhe: str = Field(default="", max_length=1000)
    registrado_em: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        index=True,
    )
