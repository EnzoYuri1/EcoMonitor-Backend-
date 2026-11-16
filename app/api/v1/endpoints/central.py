from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlmodel import Session

from app.api.v1.responses import (
    BAD_REQUEST_RESPONSE,
    UNAUTHORIZED_RESPONSE,
    VALIDATION_ERROR_RESPONSE,
)
from app.core.ratelimit import verificar_rate_limit
from app.core.security import get_current_user
from app.db.session import get_session
from app.models import User
from app.schemas.central import (
    ArtigoRead,
    AtualizacaoResultadoRead,
    BuscaUnificadaRead,
    CentralDestaquesRead,
    MonitoramentoResumoRead,
    NoticiaRead,
    PainelSaudeRead,
)
from app.schemas.common import Page
from app.services import central_service

router = APIRouter(
    prefix="/central",
    tags=["Central Ambiental"],
    dependencies=[Depends(verificar_rate_limit)],
)


@router.get(
    "/destaques",
    response_model=CentralDestaquesRead,
    operation_id="central_destaques_obter",
    summary="Obter destaques da Central de Informações Ambientais",
    description=(
        "Retorna a página inicial da Central de Informações Ambientais com "
        "destaques recentes, últimas notícias sobre queimadas e desmatamento, "
        "pesquisas científicas recentes, indicadores oficiais do INPE e "
        "datas de última atualização."
    ),
    response_description="Destaques da Central retornados com sucesso.",
)
def obter_destaques(
    session: Session = Depends(get_session),
) -> CentralDestaquesRead:
    return central_service.obter_destaques_central(session)


@router.get(
    "/noticias",
    response_model=Page[NoticiaRead],
    operation_id="central_noticias_listar",
    summary="Listar notícias ambientais com filtros e paginação",
    description=(
        "Lista notícias ambientais coletadas de feeds RSS especializados e "
        "APIs jornalísticas, com identificação da fonte original e separação "
        "entre data de publicação e data de coleta."
    ),
    response_description="Lista paginada de notícias ambientais.",
    responses={
        400: BAD_REQUEST_RESPONSE,
        422: VALIDATION_ERROR_RESPONSE,
    },
)
def listar_noticias(
    categoria: str | None = Query(
        default=None,
        max_length=40,
        description=(
            "Filtro de categoria: todas, brasileiras, internacionais, "
            "queimadas, desmatamento, amazonia, para, clima, fiscalizacao, preservacao."
        ),
        examples=["queimadas"],
    ),
    idioma: str | None = Query(
        default="pt",
        pattern="^(pt|en|todos)$",
        description="Idioma das notícias: pt (brasileiras, padrão), en (internacionais) ou todos.",
        examples=["pt"],
    ),
    termo: str | None = Query(
        default=None,
        min_length=2,
        max_length=120,
        description="Termo de busca no título, resumo ou veículo.",
        examples=["Amazônia"],
    ),
    veiculo: str | None = Query(
        default=None,
        max_length=100,
        description="Filtrar por nome do veículo de comunicação.",
        examples=["Mongabay"],
    ),
    data_inicio: date | None = Query(
        default=None,
        description="Data inicial de publicação (AAAA-MM-DD).",
        examples=["2026-01-01"],
    ),
    data_fim: date | None = Query(
        default=None,
        description="Data final de publicação (AAAA-MM-DD).",
        examples=["2026-12-31"],
    ),
    ordenar: str = Query(
        default="recentes",
        pattern="^(recentes|relevancia)$",
        description="Ordenação: recentes ou relevancia.",
        examples=["recentes"],
    ),
    page: int = Query(default=1, ge=1, examples=[1]),
    page_size: int = Query(default=12, ge=1, le=50, examples=[12]),
    session: Session = Depends(get_session),
) -> Page[NoticiaRead]:
    if (
        data_inicio is not None
        and data_fim is not None
        and data_inicio > data_fim
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A data inicial não pode ser posterior à data final.",
        )

    return central_service.listar_noticias(
        session,
        categoria=categoria,
        idioma=idioma,
        termo=termo,
        veiculo=veiculo,
        data_inicio=data_inicio,
        data_fim=data_fim,
        ordenar=ordenar,
        page=page,
        page_size=page_size,
    )


@router.get(
    "/artigos",
    response_model=Page[ArtigoRead],
    operation_id="central_artigos_listar",
    summary="Listar artigos científicos e pesquisas acadêmicas",
    description=(
        "Consulta a biblioteca de artigos científicos indexados via OpenAlex, "
        "SciELO e Crossref, com DOI, autores, periódico, resumo e ano."
    ),
    response_description="Lista paginada de artigos científicos.",
    responses={422: VALIDATION_ERROR_RESPONSE},
)
def listar_artigos(
    filtro: str | None = Query(
        default="todos",
        max_length=40,
        description=(
            "Filtro: todos, recentes, relevantes, queimadas, desmatamento, "
            "biodiversidade, clima, amazonia, brasileiras, internacionais."
        ),
        examples=["amazonia"],
    ),
    termo: str | None = Query(
        default=None,
        min_length=2,
        max_length=120,
        description="Busca por título, autor, resumo ou palavras-chave.",
        examples=["deforestation"],
    ),
    ano: int | None = Query(
        default=None,
        ge=1950,
        le=2100,
        description="Filtrar por ano de publicação.",
        examples=[2024],
    ),
    ordenar: str = Query(
        default="recentes",
        pattern="^(recentes|relevantes)$",
        description="Ordenação: recentes ou relevantes (por citações).",
        examples=["recentes"],
    ),
    page: int = Query(default=1, ge=1, examples=[1]),
    page_size: int = Query(default=10, ge=1, le=50, examples=[10]),
    session: Session = Depends(get_session),
) -> Page[ArtigoRead]:
    return central_service.listar_artigos(
        session,
        filtro=filtro,
        termo=termo,
        ano=ano,
        ordenar=ordenar,
        page=page,
        page_size=page_size,
    )


@router.get(
    "/monitoramento",
    response_model=MonitoramentoResumoRead,
    operation_id="central_monitoramento_obter",
    summary="Obter dados oficiais de monitoramento ambiental (INPE / NASA FIRMS)",
    description=(
        "Apresenta indicadores oficiais diferenciando claramente focos de calor "
        "(Programa Queimadas/INPE e NASA FIRMS), alertas operacionais de "
        "desmatamento (DETER/INPE) e taxas anuais consolidadas de desmatamento "
        "(PRODES/INPE), com destaque para o Estado do Pará e a Amazônia Legal."
    ),
    response_description="Painel de monitoramento ambiental oficial.",
    responses={422: VALIDATION_ERROR_RESPONSE},
)
def obter_monitoramento(
    estado: str | None = Query(
        default=None,
        min_length=2,
        max_length=2,
        description="Sigla da UF (ex.: PA, AM, MT).",
        examples=["PA"],
    ),
    tipo_metrica: str | None = Query(
        default=None,
        pattern="^(foco_de_calor|alerta_desmatamento|desmatamento_consolidado)$",
        description="Filtrar registros por tipo de métrica oficial.",
        examples=["foco_de_calor"],
    ),
    apenas_amazonia_legal: bool = Query(
        default=False,
        description="Restringir aos 9 estados da Amazônia Legal.",
    ),
    session: Session = Depends(get_session),
) -> MonitoramentoResumoRead:
    return central_service.obter_resumo_monitoramento(
        session,
        estado=estado,
        tipo_metrica=tipo_metrica,
        apenas_amazonia_legal=apenas_amazonia_legal,
    )


@router.get(
    "/busca",
    response_model=BuscaUnificadaRead,
    operation_id="central_busca_inteligente",
    summary="Pesquisar de forma integrada em notícias, artigos e dados oficiais",
    description=(
        "Mecanismo de busca inteligente da Central Ambiental. Interpreta o "
        "assunto pesquisado, consulta as categorias compatíveis sem inventar "
        "dados e organiza os resultados identificando cada origem."
    ),
    response_description="Resultados unificados da pesquisa.",
    responses={
        400: BAD_REQUEST_RESPONSE,
        422: VALIDATION_ERROR_RESPONSE,
    },
)
def buscar_na_central(
    q: str = Query(
        ...,
        min_length=2,
        max_length=150,
        description="Termo ou expressão de pesquisa.",
        examples=["Queimadas no Pará"],
    ),
    escopo: str = Query(
        default="todas",
        pattern="^(todas|noticias|artigos|dados_oficiais)$",
        description="Fontes: todas, noticias, artigos ou dados_oficiais.",
        examples=["todas"],
    ),
    ordenar: str = Query(
        default="relevancia",
        pattern="^(relevancia|data)$",
        description="Ordenação dos resultados: relevancia ou data.",
        examples=["relevancia"],
    ),
    data_inicio: date | None = Query(
        default=None,
        description="Data inicial opcional (AAAA-MM-DD).",
    ),
    data_fim: date | None = Query(
        default=None,
        description="Data final opcional (AAAA-MM-DD).",
    ),
    session: Session = Depends(get_session),
) -> BuscaUnificadaRead:
    if (
        data_inicio is not None
        and data_fim is not None
        and data_inicio > data_fim
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A data inicial não pode ser posterior à data final.",
        )

    return central_service.buscar_inteligente(
        session,
        q=q,
        escopo=escopo,
        ordenar=ordenar,
        data_inicio=data_inicio,
        data_fim=data_fim,
    )


@router.get(
    "/status",
    response_model=PainelSaudeRead,
    operation_id="central_status_obter",
    summary="Consultar painel de saúde do sistema e status das integrações",
    description=(
        "Retorna o estado operacional do backend, banco de dados, última "
        "atualização de cada módulo e status real de cada integração externa."
    ),
    response_description="Painel de saúde e integrações.",
)
def obter_status_saude(
    session: Session = Depends(get_session),
) -> PainelSaudeRead:
    return central_service.obter_painel_saude(session)


@router.post(
    "/atualizar",
    response_model=AtualizacaoResultadoRead,
    operation_id="central_atualizar_executar",
    summary="Disparar atualização das fontes externas (requer autenticação)",
    description=(
        "Executa sob demanda a coleta de notícias, artigos científicos e/ou "
        "dados oficiais de monitoramento ambiental. Exige Bearer token."
    ),
    response_description="Coleta executada e registrada no cache.",
    responses={
        401: UNAUTHORIZED_RESPONSE,
        422: VALIDATION_ERROR_RESPONSE,
    },
)
def disparar_atualizacao(
    escopo: str = Query(
        default="todas",
        pattern="^(todas|noticias|artigos|monitoramento)$",
        description="Escopo da atualização: todas, noticias, artigos ou monitoramento.",
        examples=["todas"],
    ),
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> AtualizacaoResultadoRead:
    return central_service.executar_atualizacao_central(session, escopo=escopo)
