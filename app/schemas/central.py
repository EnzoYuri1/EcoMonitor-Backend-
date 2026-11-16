from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field


class NoticiaRead(BaseModel):
    """Representação pública de uma notícia ambiental."""

    id: int
    titulo: str
    descricao: str
    imagem_url: str | None = None
    veiculo: str
    origem_integracao: str
    url_original: str
    data_publicacao: datetime | None = None
    categoria: str
    idioma: str
    coletado_em: datetime

    model_config = ConfigDict(from_attributes=True)


class ArtigoRead(BaseModel):
    """Representação pública de um artigo científico."""

    id: int
    titulo: str
    autores: str
    instituicao_ou_periodico: str
    ano_publicacao: int | None = None
    resumo: str
    palavras_chave: str
    doi: str | None = None
    url_original: str
    base_origem: str
    categoria: str
    citacoes: int = 0
    pesquisa_brasileira: bool = False
    coletado_em: datetime

    model_config = ConfigDict(from_attributes=True)


class DadoAmbientalRead(BaseModel):
    """Representação pública de indicador ou dado oficial de monitoramento."""

    id: int
    tipo_metrica: str
    fonte: str
    instituicao: str
    estado: str
    municipio: str | None = None
    bioma: str
    amazonia_legal: bool
    latitude: float | None = None
    longitude: float | None = None
    data_referencia: date
    periodo_rotulo: str
    valor: float
    unidade: str
    satelite_ou_metodo: str | None = None
    nivel_confianca: str
    url_fonte: str
    observacao: str | None = None
    coletado_em: datetime

    model_config = ConfigDict(from_attributes=True)


class IntegracaoStatusRead(BaseModel):
    """Estado de uma integração externa."""

    chave: str
    nome: str
    categoria: str
    status: str
    configurada: bool
    ultima_tentativa: datetime | None = None
    ultima_atualizacao: datetime | None = None
    total_itens_ultima_coleta: int
    mensagem: str
    url_documentacao: str

    model_config = ConfigDict(from_attributes=True)


class MonitoramentoEstadoResumo(BaseModel):
    """Totais oficiais agregados por estado e tipo de métrica."""

    estado: str
    amazonia_legal: bool
    focos_calor_total: float = 0.0
    alertas_deter_km2: float = 0.0
    desmatamento_prodes_km2: float = 0.0


class MonitoramentoResumoRead(BaseModel):
    """Painel consolidado de monitoramento oficial com distinção de métricas."""

    focos_calor_brasil: float = 0.0
    focos_calor_amazonia_legal: float = 0.0
    focos_calor_para: float = 0.0
    alertas_deter_amazonia_km2: float = 0.0
    alertas_deter_para_km2: float = 0.0
    prodes_amazonia_ultimo_ano_km2: float = 0.0
    prodes_para_ultimo_ano_km2: float = 0.0
    prodes_ano_referencia: int | None = None
    ultima_coleta: datetime | None = None
    nota_metodologica: str = (
        "Focos de calor (INPE/NASA FIRMS), alertas de desmatamento em tempo "
        "quase real (DETER/INPE) e taxas anuais consolidadas (PRODES/INPE) "
        "são métricas distintas e não equivalentes."
    )
    por_estado: list[MonitoramentoEstadoResumo] = Field(default_factory=list)
    historico_prodes: list[DadoAmbientalRead] = Field(default_factory=list)
    registros_recentes: list[DadoAmbientalRead] = Field(default_factory=list)


class CentralDestaquesRead(BaseModel):
    """Página inicial da Central de Informações Ambientais."""

    destaques_recentes: list[NoticiaRead] = Field(default_factory=list)
    ultimas_queimadas: list[NoticiaRead] = Field(default_factory=list)
    ultimas_desmatamento: list[NoticiaRead] = Field(default_factory=list)
    pesquisas_recentes: list[ArtigoRead] = Field(default_factory=list)
    monitoramento: MonitoramentoResumoRead
    ultima_atualizacao_noticias: datetime | None = None
    ultima_atualizacao_artigos: datetime | None = None
    ultima_atualizacao_monitoramento: datetime | None = None
    total_noticias: int = 0
    total_artigos: int = 0
    total_indicadores: int = 0


class BuscaUnificadaItem(BaseModel):
    """Item retornado na busca inteligente unificada."""

    tipo_fonte: str
    id: int
    titulo: str
    resumo: str
    origem: str
    instituicao_ou_veiculo: str
    categoria: str
    data_referencia: str | None = None
    coletado_em: datetime
    url_original: str
    doi: str | None = None
    relevancia: float = 1.0


class BuscaUnificadaRead(BaseModel):
    """Resposta da busca inteligente da Central."""

    termo: str
    escopo: str
    ordenacao: str
    total: int
    total_noticias: int
    total_artigos: int
    total_dados_oficiais: int
    noticias: list[NoticiaRead] = Field(default_factory=list)
    artigos: list[ArtigoRead] = Field(default_factory=list)
    dados_oficiais: list[DadoAmbientalRead] = Field(default_factory=list)
    resultados: list[BuscaUnificadaItem] = Field(default_factory=list)


class AtualizacaoResultadoRead(BaseModel):
    """Resultado de uma execução de coleta/atualização."""

    escopo: str
    executado_em: datetime
    noticias_novas: int = 0
    artigos_novos: int = 0
    indicadores_atualizados: int = 0
    integracoes: list[IntegracaoStatusRead] = Field(default_factory=list)


class PainelSaudeRead(BaseModel):
    """Painel de saúde do sistema e status das integrações."""

    status_backend: str = "online"
    status_banco: str = "online"
    total_usuarios: int = 0
    total_ocorrencias: int = 0
    total_noticias: int = 0
    total_artigos: int = 0
    total_dados_ambientais: int = 0
    ultima_atualizacao_noticias: datetime | None = None
    ultima_atualizacao_artigos: datetime | None = None
    ultima_atualizacao_monitoramento: datetime | None = None
    integracoes: list[IntegracaoStatusRead] = Field(default_factory=list)
    fontes_documentadas_limitacoes: list[dict[str, str]] = Field(
        default_factory=list
    )
    verificado_em: datetime
