from collections import defaultdict
from datetime import date, datetime, timezone
import math
import time

from sqlmodel import Session, col, func, or_, select

from app.integrations.base import (
    ESTADOS_AMAZONIA_LEGAL,
    IntegrationError,
    normalizar_doi,
    normalizar_url,
)
from app.integrations.firms import coletar_focos_firms_para, firms_configurada
from app.integrations.gnews import coletar_noticias_gnews, gnews_configurada
from app.integrations.inpe_queimadas import coletar_focos_inpe_diario
from app.integrations.openalex import (
    coletar_artigos_crossref,
    coletar_artigos_openalex,
)
from app.integrations.rss import carregar_fontes_rss, coletar_feed_rss
from app.integrations.terrabrasilis import (
    SERIE_HISTORICA_OFICIAL_PRODES,
    coletar_deter_terrabrasilis,
    gerar_registros_serie_prodes,
    verificar_wfs_prodes_E_gerar_serie,
)
from app.models import Ocorrencia, User
from app.models.central import (
    ArtigoCientifico,
    DadoAmbientalOficial,
    IntegracaoLog,
    IntegracaoStatus,
    Noticia,
)
from app.schemas.central import (
    ArtigoRead,
    AtualizacaoResultadoRead,
    BuscaUnificadaItem,
    BuscaUnificadaRead,
    CentralDestaquesRead,
    DadoAmbientalRead,
    IntegracaoStatusRead,
    MonitoramentoEstadoResumo,
    MonitoramentoResumoRead,
    NoticiaRead,
    PainelSaudeRead,
)
from app.schemas.common import Page

CATALOGO_INTEGRACOES = [
    {
        "chave": "rss_jornalistico",
        "nome": "Feeds RSS Jornalísticos e Ambientais (Mongabay, ((o))eco, Agência Brasil, G1, Folha, NASA)",
        "categoria": "noticias",
        "url_documentacao": "https://brasil.mongabay.com/feed/",
        "requer_chave": False,
    },
    {
        "chave": "gnews_api",
        "nome": "GNews API v4 (Notícias em Português)",
        "categoria": "noticias",
        "url_documentacao": "https://gnews.io/docs/v4",
        "requer_chave": True,
    },
    {
        "chave": "openalex_api",
        "nome": "OpenAlex + Indexação SciELO (Artigos Científicos)",
        "categoria": "artigos",
        "url_documentacao": "https://docs.openalex.org/",
        "requer_chave": False,
    },
    {
        "chave": "crossref_api",
        "nome": "Crossref REST API (Metadados e DOI)",
        "categoria": "artigos",
        "url_documentacao": "https://www.crossref.org/documentation/retrieve-metadata/rest-api/",
        "requer_chave": False,
    },
    {
        "chave": "inpe_queimadas",
        "nome": "INPE — Programa Queimadas (CSV Diário BDQueimadas)",
        "categoria": "monitoramento",
        "url_documentacao": "https://terrabrasilis.dpi.inpe.br/queimadas/portal/",
        "requer_chave": False,
    },
    {
        "chave": "inpe_terrabrasilis_deter",
        "nome": "INPE — TerraBrasilis DETER (Alertas WFS Amazônia Legal)",
        "categoria": "monitoramento",
        "url_documentacao": "https://terrabrasilis.dpi.inpe.br/",
        "requer_chave": False,
    },
    {
        "chave": "inpe_terrabrasilis_prodes",
        "nome": "INPE — TerraBrasilis PRODES (Desmatamento Consolidado Amazônia Legal)",
        "categoria": "monitoramento",
        "url_documentacao": "https://terrabrasilis.dpi.inpe.br/",
        "requer_chave": False,
    },
    {
        "chave": "nasa_firms",
        "nome": "NASA FIRMS (Satélites VIIRS/MODIS)",
        "categoria": "monitoramento",
        "url_documentacao": "https://firms.modaps.eosdis.nasa.gov/api/",
        "requer_chave": True,
    },
]

FONTES_LIMITACOES_DOCUMENTADAS = [
    {
        "fonte": "MapBiomas Alerta (GraphQL v2)",
        "url_oficial": "https://plataforma.alerta.mapbiomas.org/api",
        "situacao": "Documentada — requer conta autenticada e token próprio",
        "explicacao": (
            "A API GraphQL v2 do MapBiomas Alerta exige autenticação mediante "
            "credenciais de conta (mutation SignIn). Conforme diretriz técnica, "
            "não há simulação de dados; o acesso oficial pode ser consultado "
            "diretamente na plataforma MapBiomas."
        ),
    },
    {
        "fonte": "NewsAPI.org (Developer Plan)",
        "url_oficial": "https://newsapi.org/docs",
        "situacao": "Desativada em produção/homologação por restrição de licença",
        "explicacao": (
            "O plano gratuito da NewsAPI restringe o uso exclusivamente a localhost "
            "e aplica atraso de 24h nos artigos. A Central prioriza feeds RSS diretos "
            "dos veículos e GNews API opcional."
        ),
    },
    {
        "fonte": "SciELO (ArticleMeta / OpenAlex)",
        "url_oficial": "https://scielo.org/",
        "situacao": "Integrada via indexador aberto OpenAlex (indexed_in:scielo)",
        "explicacao": (
            "A API ArticleMeta nativa do SciELO é voltada à coleta de coleções e "
            "fascículos sem busca temática full-text; por isso os periódicos SciELO "
            "são consultados diretamente pelo índice OpenAlex com identificação da origem."
        ),
    },
]


def garantir_catalogo_integracoes(session: Session) -> list[IntegracaoStatus]:
    """Garante que todas as integrações do catálogo existam na tabela de status."""
    existentes = list(
        session.exec(
            select(IntegracaoStatus).order_by(IntegracaoStatus.id)
        ).all()
    )
    if len(existentes) >= len(CATALOGO_INTEGRACOES):
        return existentes

    mapa_existentes = {item.chave: item for item in existentes}
    alterado = False

    for meta in CATALOGO_INTEGRACOES:
        chave = meta["chave"]
        configurada = True
        if chave == "gnews_api":
            configurada = gnews_configurada()
        elif chave == "nasa_firms":
            configurada = firms_configurada()

        if chave not in mapa_existentes:
            novo = IntegracaoStatus(
                chave=chave,
                nome=meta["nome"],
                categoria=meta["categoria"],
                status="nao_executada" if configurada else "requer_chave",
                configurada=configurada,
                mensagem=(
                    "Aguardando primeira coleta programada."
                    if configurada
                    else "Chave opcional não configurada no arquivo .env."
                ),
                url_documentacao=meta["url_documentacao"],
            )
            session.add(novo)
            mapa_existentes[chave] = novo
            alterado = True

    if alterado:
        session.commit()

    return list(
        session.exec(
            select(IntegracaoStatus).order_by(IntegracaoStatus.id)
        ).all()
    )


def _registrar_execucao_integracao(
    session: Session,
    *,
    chave: str,
    sucesso: bool,
    itens: int,
    duracao_ms: int,
    mensagem: str,
    configurada: bool = True,
) -> None:
    garantir_catalogo_integracoes(session)
    agora = datetime.now(timezone.utc)
    registro = session.exec(
        select(IntegracaoStatus).where(IntegracaoStatus.chave == chave)
    ).first()

    novo_status = (
        "operacional"
        if sucesso
        else ("requer_chave" if not configurada else "indisponivel")
    )

    if registro:
        registro.ultima_tentativa = agora
        registro.configurada = configurada
        registro.status = novo_status
        registro.mensagem = mensagem[:950]
        if sucesso:
            registro.ultima_atualizacao = agora
            registro.total_itens_ultima_coleta = itens
        session.add(registro)

    log = IntegracaoLog(
        chave_integracao=chave,
        status=novo_status,
        itens_processados=itens,
        duracao_ms=max(duracao_ms, 0),
        detalhe=mensagem[:950],
        registrado_em=agora,
    )
    session.add(log)
    session.commit()


def salvar_noticias_deduplicadas(
    session: Session, itens: list[dict]
) -> int:
    """Insere ou atualiza notícias evitando duplicidade por URL normalizada."""
    inseridas = 0
    agora = datetime.now(timezone.utc)
    urls_vistas: set[str] = set()

    for dados in itens:
        url_norm = normalizar_url(
            dados.get("url_normalizada") or dados.get("url_original") or ""
        )
        titulo = (dados.get("titulo") or "").strip()
        if not url_norm or not titulo or url_norm in urls_vistas:
            continue
        urls_vistas.add(url_norm)

        existente = session.exec(
            select(Noticia).where(Noticia.url_normalizada == url_norm)
        ).first()

        if existente:
            existente.coletado_em = agora
            if not existente.imagem_url and dados.get("imagem_url"):
                existente.imagem_url = dados.get("imagem_url")
            session.add(existente)
        else:
            nova = Noticia(
                titulo=titulo[:500],
                descricao=(dados.get("descricao") or "")[:2000],
                imagem_url=dados.get("imagem_url"),
                veiculo=(dados.get("veiculo") or "Fonte jornalística")[:160],
                origem_integracao=(dados.get("origem_integracao") or "rss")[:80],
                url_original=(dados.get("url_original") or url_norm)[:1000],
                url_normalizada=url_norm[:1000],
                data_publicacao=dados.get("data_publicacao"),
                categoria=(dados.get("categoria") or "preservacao")[:40],
                idioma=(dados.get("idioma") or "pt")[:10],
                coletado_em=agora,
            )
            session.add(nova)
            inseridas += 1

    session.commit()
    return inseridas


def salvar_artigos_deduplicados(
    session: Session, itens: list[dict]
) -> int:
    """Insere ou atualiza artigos científicos evitando duplicidade por DOI ou ID único."""
    inseridos = 0
    agora = datetime.now(timezone.utc)
    vistos: set[str] = set()

    for dados in itens:
        titulo = (dados.get("titulo") or "").strip()
        if not titulo:
            continue
        doi = normalizar_doi(dados.get("doi"))
        ident = (
            f"doi:{doi}"
            if doi
            else (
                dados.get("identificador_unico")
                or f"titulo:{titulo.lower()[:160]}"
            )
        )[:320]
        if ident in vistos:
            continue
        vistos.add(ident)

        existente = session.exec(
            select(ArtigoCientifico).where(
                ArtigoCientifico.identificador_unico == ident
            )
        ).first()
        if not existente and doi:
            existente = session.exec(
                select(ArtigoCientifico).where(ArtigoCientifico.doi == doi)
            ).first()

        if existente:
            existente.coletado_em = agora
            existente.citacoes = max(
                existente.citacoes, int(dados.get("citacoes") or 0)
            )
            if (
                "não disponibilizado" in existente.resumo.lower()
                and dados.get("resumo")
                and "não disponibilizado" not in str(dados.get("resumo")).lower()
            ):
                existente.resumo = str(dados.get("resumo"))[:4000]
            session.add(existente)
        else:
            novo = ArtigoCientifico(
                titulo=titulo[:800],
                autores=(dados.get("autores") or "Autores não informados")[:1500],
                instituicao_ou_periodico=(
                    dados.get("instituicao_ou_periodico") or "Periódico científico"
                )[:400],
                ano_publicacao=dados.get("ano_publicacao"),
                resumo=(dados.get("resumo") or "")[:4000],
                palavras_chave=(dados.get("palavras_chave") or "")[:800],
                doi=doi,
                identificador_unico=ident,
                url_original=(dados.get("url_original") or "")[:1000],
                base_origem=(dados.get("base_origem") or "OpenAlex")[:80],
                categoria=(dados.get("categoria") or "amazonia")[:40],
                citacoes=int(dados.get("citacoes") or 0),
                pesquisa_brasileira=bool(dados.get("pesquisa_brasileira", False)),
                coletado_em=agora,
            )
            session.add(novo)
            inseridos += 1

    session.commit()
    return inseridos


def salvar_dados_ambientais_deduplicados(
    session: Session, itens: list[dict]
) -> int:
    """Insere ou atualiza indicadores oficiais usando identificador_original único."""
    processados = 0
    agora = datetime.now(timezone.utc)
    vistos: set[str] = set()

    for dados in itens:
        ident = (dados.get("identificador_original") or "").strip()[:255]
        if not ident or ident in vistos:
            continue
        vistos.add(ident)

        existente = session.exec(
            select(DadoAmbientalOficial).where(
                DadoAmbientalOficial.identificador_original == ident
            )
        ).first()

        if existente:
            existente.valor = float(dados.get("valor") or 0.0)
            existente.data_referencia = dados.get(
                "data_referencia", existente.data_referencia
            )
            existente.periodo_rotulo = (
                dados.get("periodo_rotulo") or existente.periodo_rotulo
            )[:80]
            existente.observacao = (
                dados.get("observacao") or existente.observacao
            )
            existente.coletado_em = agora
            session.add(existente)
        else:
            novo = DadoAmbientalOficial(
                tipo_metrica=(dados.get("tipo_metrica") or "foco_de_calor")[:40],
                fonte=(dados.get("fonte") or "INPE")[:120],
                instituicao=(dados.get("instituicao") or "INPE / MCTI")[:160],
                identificador_original=ident,
                estado=(dados.get("estado") or "PA")[:2].upper(),
                municipio=dados.get("municipio"),
                bioma=(dados.get("bioma") or "Amazônia")[:80],
                amazonia_legal=bool(dados.get("amazonia_legal", True)),
                latitude=dados.get("latitude"),
                longitude=dados.get("longitude"),
                data_referencia=dados.get("data_referencia") or date.today(),
                periodo_rotulo=(dados.get("periodo_rotulo") or "")[:80],
                valor=float(dados.get("valor") or 0.0),
                unidade=(dados.get("unidade") or "focos")[:40],
                satelite_ou_metodo=dados.get("satelite_ou_metodo"),
                nivel_confianca=(dados.get("nivel_confianca") or "oficial")[:40],
                url_fonte=(dados.get("url_fonte") or "")[:1000],
                observacao=dados.get("observacao"),
                coletado_em=agora,
            )
            session.add(novo)
        processados += 1

    session.commit()
    return processados


def garantir_serie_prodes_inicial(session: Session) -> None:
    """Garante que a série histórica oficial consolidada do PRODES esteja presente no banco."""
    total_prodes = session.exec(
        select(func.count(DadoAmbientalOficial.id)).where(
            DadoAmbientalOficial.tipo_metrica == "desmatamento_consolidado"
        )
    ).one()
    if int(total_prodes or 0) == 0:
        salvar_dados_ambientais_deduplicados(
            session, gerar_registros_serie_prodes()
        )


def atualizar_noticias(session: Session) -> int:
    """Executa a coleta de todas as fontes de notícias configuradas."""
    novas_total = 0

    # 1. Feeds RSS
    inicio = time.monotonic()
    fontes = carregar_fontes_rss()
    coletadas_rss: list[dict] = []
    erros_rss: list[str] = []

    for fonte in fontes:
        try:
            coletadas_rss.extend(coletar_feed_rss(fonte, limite=18))
        except Exception as exc:  # noqa: BLE001
            erros_rss.append(f"{fonte.get('nome')}: {exc}")

    duracao_rss = int((time.monotonic() - inicio) * 1000)
    if coletadas_rss:
        novas_rss = salvar_noticias_deduplicadas(session, coletadas_rss)
        novas_total += novas_rss
        msg = (
            f"{len(coletadas_rss)} notícias lidas de {len(fontes)} feeds RSS "
            f"({novas_rss} novas)."
        )
        if erros_rss:
            msg += f" Avisos parciais: {'; '.join(erros_rss[:2])}"
        _registrar_execucao_integracao(
            session,
            chave="rss_jornalistico",
            sucesso=True,
            itens=len(coletadas_rss),
            duracao_ms=duracao_rss,
            mensagem=msg,
        )
    else:
        _registrar_execucao_integracao(
            session,
            chave="rss_jornalistico",
            sucesso=False,
            itens=0,
            duracao_ms=duracao_rss,
            mensagem=(
                "Não foi possível coletar feeds RSS: "
                + ("; ".join(erros_rss[:3]) if erros_rss else "nenhuma fonte ativa.")
            ),
        )

    # 2. GNews API (opcional)
    inicio_gnews = time.monotonic()
    if gnews_configurada():
        try:
            itens_gnews = coletar_noticias_gnews(max_por_consulta=10)
            novas_gnews = salvar_noticias_deduplicadas(session, itens_gnews)
            novas_total += novas_gnews
            _registrar_execucao_integracao(
                session,
                chave="gnews_api",
                sucesso=True,
                itens=len(itens_gnews),
                duracao_ms=int((time.monotonic() - inicio_gnews) * 1000),
                mensagem=f"{len(itens_gnews)} notícias obtidas da GNews API ({novas_gnews} novas).",
                configurada=True,
            )
        except Exception as exc:  # noqa: BLE001
            _registrar_execucao_integracao(
                session,
                chave="gnews_api",
                sucesso=False,
                itens=0,
                duracao_ms=int((time.monotonic() - inicio_gnews) * 1000),
                mensagem=f"Falha ao consultar GNews API: {exc}",
                configurada=True,
            )
    else:
        _registrar_execucao_integracao(
            session,
            chave="gnews_api",
            sucesso=False,
            itens=0,
            duracao_ms=0,
            mensagem="Chave opcional GNEWS_API_KEY não configurada; usando RSS como fonte principal.",
            configurada=False,
        )

    return novas_total


def atualizar_artigos(session: Session) -> int:
    """Executa a coleta de artigos científicos no OpenAlex e Crossref."""
    novos_total = 0

    # 1. OpenAlex
    inicio_oa = time.monotonic()
    try:
        itens_oa = coletar_artigos_openalex(por_consulta=8)
        novos_oa = salvar_artigos_deduplicados(session, itens_oa)
        novos_total += novos_oa
        _registrar_execucao_integracao(
            session,
            chave="openalex_api",
            sucesso=True,
            itens=len(itens_oa),
            duracao_ms=int((time.monotonic() - inicio_oa) * 1000),
            mensagem=f"{len(itens_oa)} artigos processados via OpenAlex ({novos_oa} novos).",
        )
    except Exception as exc:  # noqa: BLE001
        _registrar_execucao_integracao(
            session,
            chave="openalex_api",
            sucesso=False,
            itens=0,
            duracao_ms=int((time.monotonic() - inicio_oa) * 1000),
            mensagem=f"Erro ao consultar OpenAlex: {exc}",
        )

    # 2. Crossref
    inicio_cr = time.monotonic()
    try:
        itens_cr = coletar_artigos_crossref(linhas=8)
        novos_cr = salvar_artigos_deduplicados(session, itens_cr)
        novos_total += novos_cr
        _registrar_execucao_integracao(
            session,
            chave="crossref_api",
            sucesso=True,
            itens=len(itens_cr),
            duracao_ms=int((time.monotonic() - inicio_cr) * 1000),
            mensagem=f"{len(itens_cr)} publicações verificadas via Crossref ({novos_cr} novas).",
        )
    except Exception as exc:  # noqa: BLE001
        _registrar_execucao_integracao(
            session,
            chave="crossref_api",
            sucesso=False,
            itens=0,
            duracao_ms=int((time.monotonic() - inicio_cr) * 1000),
            mensagem=f"Erro ao consultar Crossref: {exc}",
        )

    return novos_total


def atualizar_monitoramento(session: Session) -> int:
    """Executa a coleta de dados oficiais do INPE (Queimadas, DETER, PRODES) e NASA FIRMS."""
    processados_total = 0

    # 1. INPE Queimadas CSV diário
    inicio_inpe = time.monotonic()
    try:
        itens_focos = coletar_focos_inpe_diario()
        proc_focos = salvar_dados_ambientais_deduplicados(session, itens_focos)
        processados_total += proc_focos
        _registrar_execucao_integracao(
            session,
            chave="inpe_queimadas",
            sucesso=True,
            itens=len(itens_focos),
            duracao_ms=int((time.monotonic() - inicio_inpe) * 1000),
            mensagem=(
                f"Consolidado diário do INPE processado com sucesso "
                f"({len(itens_focos)} agregados estaduais/municipais)."
            ),
        )
    except Exception as exc:  # noqa: BLE001
        _registrar_execucao_integracao(
            session,
            chave="inpe_queimadas",
            sucesso=False,
            itens=0,
            duracao_ms=int((time.monotonic() - inicio_inpe) * 1000),
            mensagem=f"Falha ao obter CSV diário do INPE: {exc}",
        )

    # 2. INPE TerraBrasilis DETER WFS
    inicio_deter = time.monotonic()
    try:
        itens_deter = coletar_deter_terrabrasilis(limite_feicoes=120)
        proc_deter = salvar_dados_ambientais_deduplicados(session, itens_deter)
        processados_total += proc_deter
        _registrar_execucao_integracao(
            session,
            chave="inpe_terrabrasilis_deter",
            sucesso=True,
            itens=len(itens_deter),
            duracao_ms=int((time.monotonic() - inicio_deter) * 1000),
            mensagem=f"{len(itens_deter)} indicadores de alertas DETER atualizados via WFS.",
        )
    except Exception as exc:  # noqa: BLE001
        _registrar_execucao_integracao(
            session,
            chave="inpe_terrabrasilis_deter",
            sucesso=False,
            itens=0,
            duracao_ms=int((time.monotonic() - inicio_deter) * 1000),
            mensagem=f"Falha ao consultar WFS DETER do TerraBrasilis: {exc}",
        )

    # 3. INPE TerraBrasilis PRODES
    inicio_prodes = time.monotonic()
    try:
        itens_prodes = verificar_wfs_prodes_E_gerar_serie()
        proc_prodes = salvar_dados_ambientais_deduplicados(
            session, itens_prodes
        )
        processados_total += proc_prodes
        _registrar_execucao_integracao(
            session,
            chave="inpe_terrabrasilis_prodes",
            sucesso=True,
            itens=len(itens_prodes),
            duracao_ms=int((time.monotonic() - inicio_prodes) * 1000),
            mensagem=(
                "WFS PRODES verificado e série consolidada da Amazônia Legal "
                "e do Pará atualizada."
            ),
        )
    except Exception as exc:  # noqa: BLE001
        # Mesmo se o WFS oscilar, mantém a série oficial consolidada disponível
        garantir_serie_prodes_inicial(session)
        _registrar_execucao_integracao(
            session,
            chave="inpe_terrabrasilis_prodes",
            sucesso=False,
            itens=0,
            duracao_ms=int((time.monotonic() - inicio_prodes) * 1000),
            mensagem=f"WFS PRODES indisponível no momento ({exc}); exibindo série histórica armazenada.",
        )

    # 4. NASA FIRMS (opcional)
    inicio_firms = time.monotonic()
    if firms_configurada():
        try:
            itens_firms = coletar_focos_firms_para()
            proc_firms = salvar_dados_ambientais_deduplicados(
                session, itens_firms
            )
            processados_total += proc_firms
            _registrar_execucao_integracao(
                session,
                chave="nasa_firms",
                sucesso=True,
                itens=len(itens_firms),
                duracao_ms=int((time.monotonic() - inicio_firms) * 1000),
                mensagem="Dados orbitais VIIRS/NASA FIRMS atualizados para o Pará.",
                configurada=True,
            )
        except Exception as exc:  # noqa: BLE001
            _registrar_execucao_integracao(
                session,
                chave="nasa_firms",
                sucesso=False,
                itens=0,
                duracao_ms=int((time.monotonic() - inicio_firms) * 1000),
                mensagem=f"Erro ao consultar NASA FIRMS: {exc}",
                configurada=True,
            )
    else:
        _registrar_execucao_integracao(
            session,
            chave="nasa_firms",
            sucesso=False,
            itens=0,
            duracao_ms=0,
            mensagem="MAP_KEY opcional (FIRMS_MAP_KEY) não configurada; focos supridos pelo INPE.",
            configurada=False,
        )

    return processados_total


def executar_atualizacao_central(
    session: Session, escopo: str = "todas"
) -> AtualizacaoResultadoRead:
    """Dispara a coleta programada para notícias, artigos, monitoramento ou todas."""
    escopo_norm = (escopo or "todas").strip().lower()
    noticias_novas = 0
    artigos_novos = 0
    indicadores_proc = 0

    if escopo_norm in {"todas", "noticias"}:
        noticias_novas = atualizar_noticias(session)
    if escopo_norm in {"todas", "artigos"}:
        artigos_novos = atualizar_artigos(session)
    if escopo_norm in {"todas", "monitoramento"}:
        indicadores_proc = atualizar_monitoramento(session)

    status_lista = garantir_catalogo_integracoes(session)
    return AtualizacaoResultadoRead(
        escopo=escopo_norm,
        executado_em=datetime.now(timezone.utc),
        noticias_novas=noticias_novas,
        artigos_novos=artigos_novos,
        indicadores_atualizados=indicadores_proc,
        integracoes=[
            IntegracaoStatusRead.model_validate(item) for item in status_lista
        ],
    )


def listar_noticias(
    session: Session,
    *,
    categoria: str | None = None,
    idioma: str | None = "pt",
    termo: str | None = None,
    veiculo: str | None = None,
    data_inicio: date | None = None,
    data_fim: date | None = None,
    ordenar: str = "recentes",
    page: int = 1,
    page_size: int = 12,
) -> Page[NoticiaRead]:
    """Consulta paginada de notícias com prioridade para notícias brasileiras (pt)."""
    filtros = []
    cat_norm = (categoria or "").strip().lower()
    if cat_norm == "brasileiras":
        filtros.append(Noticia.idioma == "pt")
    elif cat_norm == "internacionais":
        filtros.append(Noticia.idioma == "en")
    else:
        if cat_norm and cat_norm != "todas":
            filtros.append(Noticia.categoria == cat_norm)
        idioma_norm = (idioma or "").strip().lower()
        if idioma_norm in {"pt", "en"}:
            filtros.append(Noticia.idioma == idioma_norm)
    if veiculo:
        padrao_v = f"%{veiculo.strip().lower()}%"
        filtros.append(func.lower(Noticia.veiculo).like(padrao_v))
    if termo and termo.strip():
        padrao = f"%{termo.strip().lower()}%"
        filtros.append(
            or_(
                func.lower(Noticia.titulo).like(padrao),
                func.lower(Noticia.descricao).like(padrao),
                func.lower(Noticia.veiculo).like(padrao),
            )
        )
    if data_inicio is not None:
        dt_ini = datetime.combine(
            data_inicio, datetime.min.time(), tzinfo=timezone.utc
        )
        filtros.append(Noticia.data_publicacao >= dt_ini)
    if data_fim is not None:
        dt_fim = datetime.combine(
            data_fim, datetime.max.time(), tzinfo=timezone.utc
        )
        filtros.append(Noticia.data_publicacao <= dt_fim)

    total_stmt = select(func.count(Noticia.id))
    if filtros:
        total_stmt = total_stmt.where(*filtros)
    total = int(session.exec(total_stmt).one() or 0)

    stmt = select(Noticia)
    if filtros:
        stmt = stmt.where(*filtros)

    if ordenar == "relevancia" and termo:
        stmt = stmt.order_by(
            col(Noticia.data_publicacao).desc(), col(Noticia.id).desc()
        )
    else:
        stmt = stmt.order_by(
            col(Noticia.data_publicacao).desc(),
            col(Noticia.coletado_em).desc(),
            col(Noticia.id).desc(),
        )

    offset = (page - 1) * page_size
    itens = session.exec(stmt.offset(offset).limit(page_size)).all()
    pages = math.ceil(total / page_size) if total > 0 else 0

    return Page[NoticiaRead](
        items=[NoticiaRead.model_validate(i) for i in itens],
        total=total,
        page=page,
        page_size=page_size,
        pages=pages,
    )


def listar_artigos(
    session: Session,
    *,
    filtro: str | None = None,
    termo: str | None = None,
    ano: int | None = None,
    ordenar: str = "recentes",
    page: int = 1,
    page_size: int = 10,
) -> Page[ArtigoRead]:
    """Consulta paginada da biblioteca de artigos científicos."""
    condicoes = []
    filtro_norm = (filtro or "todos").strip().lower()

    if filtro_norm in {"queimadas", "desmatamento", "biodiversidade", "clima", "amazonia"}:
        condicoes.append(ArtigoCientifico.categoria == filtro_norm)
    elif filtro_norm == "brasileiras":
        condicoes.append(ArtigoCientifico.pesquisa_brasileira.is_(True))
    elif filtro_norm == "internacionais":
        condicoes.append(ArtigoCientifico.pesquisa_brasileira.is_(False))

    if ano is not None:
        condicoes.append(ArtigoCientifico.ano_publicacao == ano)

    if termo and termo.strip():
        padrao = f"%{termo.strip().lower()}%"
        condicoes.append(
            or_(
                func.lower(ArtigoCientifico.titulo).like(padrao),
                func.lower(ArtigoCientifico.resumo).like(padrao),
                func.lower(ArtigoCientifico.autores).like(padrao),
                func.lower(ArtigoCientifico.palavras_chave).like(padrao),
                func.lower(ArtigoCientifico.instituicao_ou_periodico).like(padrao),
            )
        )

    total_stmt = select(func.count(ArtigoCientifico.id))
    if condicoes:
        total_stmt = total_stmt.where(*condicoes)
    total = int(session.exec(total_stmt).one() or 0)

    stmt = select(ArtigoCientifico)
    if condicoes:
        stmt = stmt.where(*condicoes)

    if ordenar == "relevantes" or filtro_norm == "relevantes":
        stmt = stmt.order_by(
            col(ArtigoCientifico.citacoes).desc(),
            col(ArtigoCientifico.ano_publicacao).desc(),
            col(ArtigoCientifico.id).desc(),
        )
    else:
        stmt = stmt.order_by(
            col(ArtigoCientifico.ano_publicacao).desc(),
            col(ArtigoCientifico.citacoes).desc(),
            col(ArtigoCientifico.id).desc(),
        )

    offset = (page - 1) * page_size
    itens = session.exec(stmt.offset(offset).limit(page_size)).all()
    pages = math.ceil(total / page_size) if total > 0 else 0

    return Page[ArtigoRead](
        items=[ArtigoRead.model_validate(i) for i in itens],
        total=total,
        page=page,
        page_size=page_size,
        pages=pages,
    )


def obter_resumo_monitoramento(
    session: Session,
    *,
    estado: str | None = None,
    tipo_metrica: str | None = None,
    apenas_amazonia_legal: bool = False,
) -> MonitoramentoResumoRead:
    """Consolida os dados oficiais de monitoramento ambiental separando claramente as métricas."""
    garantir_serie_prodes_inicial(session)

    todos = list(
        session.exec(
            select(DadoAmbientalOficial).order_by(
                col(DadoAmbientalOficial.data_referencia).desc(),
                col(DadoAmbientalOficial.id).desc(),
            )
        ).all()
    )

    focos_brasil = 0.0
    focos_amz = 0.0
    focos_pa = 0.0
    deter_amz = 0.0
    deter_pa = 0.0

    mapa_estados: dict[str, MonitoramentoEstadoResumo] = {}
    ultima_coleta: datetime | None = None

    for reg in todos:
        if ultima_coleta is None or reg.coletado_em > ultima_coleta:
            ultima_coleta = reg.coletado_em

        uf = reg.estado
        if uf not in mapa_estados:
            mapa_estados[uf] = MonitoramentoEstadoResumo(
                estado=uf,
                amazonia_legal=uf in ESTADOS_AMAZONIA_LEGAL,
            )

        # Soma apenas agregados estaduais (municipio is None) nos KPIs gerais para não duplicar com top municípios
        if reg.tipo_metrica == "foco_de_calor" and reg.municipio is None and reg.identificador_original.startswith("inpe_focos_uf:"):
            focos_brasil += reg.valor
            if reg.amazonia_legal:
                focos_amz += reg.valor
            if uf == "PA":
                focos_pa += reg.valor
            mapa_estados[uf].focos_calor_total += reg.valor

        elif reg.tipo_metrica == "alerta_desmatamento" and reg.municipio is None:
            if reg.amazonia_legal:
                deter_amz += reg.valor
            if uf == "PA":
                deter_pa += reg.valor
            mapa_estados[uf].alertas_deter_km2 = round(
                mapa_estados[uf].alertas_deter_km2 + reg.valor, 2
            )

    ultimo_prodes = SERIE_HISTORICA_OFICIAL_PRODES[-1]
    ano_ref = int(ultimo_prodes["ano"])
    prodes_amz_ultimo = float(ultimo_prodes["amazonia_legal_km2"])
    prodes_pa_ultimo = float(ultimo_prodes["para_km2"])
    if "PA" in mapa_estados:
        mapa_estados["PA"].desmatamento_prodes_km2 = prodes_pa_ultimo

    # Filtra registros para a tabela de detalhamento conforme parâmetros
    filtrados: list[DadoAmbientalOficial] = []
    for reg in todos:
        if estado and reg.estado != estado.strip().upper():
            continue
        if tipo_metrica and reg.tipo_metrica != tipo_metrica.strip().lower():
            continue
        if apenas_amazonia_legal and not reg.amazonia_legal:
            continue
        filtrados.append(reg)

    historico_prodes = [
        DadoAmbientalRead.model_validate(r)
        for r in todos
        if r.tipo_metrica == "desmatamento_consolidado"
    ]

    por_estado_ordenado = sorted(
        mapa_estados.values(),
        key=lambda e: (
            e.estado == "PA",
            e.amazonia_legal,
            e.focos_calor_total + e.alertas_deter_km2,
        ),
        reverse=True,
    )

    return MonitoramentoResumoRead(
        focos_calor_brasil=round(focos_brasil, 0),
        focos_calor_amazonia_legal=round(focos_amz, 0),
        focos_calor_para=round(focos_pa, 0),
        alertas_deter_amazonia_km2=round(deter_amz, 2),
        alertas_deter_para_km2=round(deter_pa, 2),
        prodes_amazonia_ultimo_ano_km2=prodes_amz_ultimo,
        prodes_para_ultimo_ano_km2=prodes_pa_ultimo,
        prodes_ano_referencia=ano_ref,
        ultima_coleta=ultima_coleta,
        por_estado=por_estado_ordenado,
        historico_prodes=historico_prodes[:12],
        registros_recentes=[
            DadoAmbientalRead.model_validate(r) for r in filtrados[:30]
        ],
    )


def obter_destaques_central(session: Session) -> CentralDestaquesRead:
    """Monta os dados da página inicial da Central de Informações Ambientais."""
    garantir_catalogo_integracoes(session)
    garantir_serie_prodes_inicial(session)

    destaques = session.exec(
        select(Noticia)
        .where(Noticia.idioma == "pt")
        .order_by(col(Noticia.data_publicacao).desc(), col(Noticia.id).desc())
        .limit(6)
    ).all()

    queimadas = session.exec(
        select(Noticia)
        .where(Noticia.idioma == "pt", Noticia.categoria == "queimadas")
        .order_by(col(Noticia.data_publicacao).desc(), col(Noticia.id).desc())
        .limit(4)
    ).all()

    desmatamento = session.exec(
        select(Noticia)
        .where(
            Noticia.idioma == "pt",
            or_(
                Noticia.categoria == "desmatamento",
                Noticia.categoria == "para",
            ),
        )
        .order_by(col(Noticia.data_publicacao).desc(), col(Noticia.id).desc())
        .limit(4)
    ).all()

    pesquisas = session.exec(
        select(ArtigoCientifico)
        .order_by(
            col(ArtigoCientifico.ano_publicacao).desc(),
            col(ArtigoCientifico.citacoes).desc(),
        )
        .limit(4)
    ).all()

    total_noticias = int(
        session.exec(select(func.count(Noticia.id))).one() or 0
    )
    total_artigos = int(
        session.exec(select(func.count(ArtigoCientifico.id))).one() or 0
    )
    total_indicadores = int(
        session.exec(select(func.count(DadoAmbientalOficial.id))).one() or 0
    )

    ult_not = session.exec(select(func.max(Noticia.coletado_em))).one()
    ult_art = session.exec(
        select(func.max(ArtigoCientifico.coletado_em))
    ).one()
    ult_mon = session.exec(
        select(func.max(DadoAmbientalOficial.coletado_em))
    ).one()

    return CentralDestaquesRead(
        destaques_recentes=[NoticiaRead.model_validate(n) for n in destaques],
        ultimas_queimadas=[NoticiaRead.model_validate(n) for n in queimadas],
        ultimas_desmatamento=[
            NoticiaRead.model_validate(n) for n in desmatamento
        ],
        pesquisas_recentes=[ArtigoRead.model_validate(a) for a in pesquisas],
        monitoramento=obter_resumo_monitoramento(session),
        ultima_atualizacao_noticias=ult_not,
        ultima_atualizacao_artigos=ult_art,
        ultima_atualizacao_monitoramento=ult_mon,
        total_noticias=total_noticias,
        total_artigos=total_artigos,
        total_indicadores=total_indicadores,
    )


def _calcular_relevancia(texto_alvo: str, palavras: list[str]) -> float:
    base = (texto_alvo or "").lower()
    pontos = 0.0
    for p in palavras:
        if p in base:
            pontos += 1.0
    return pontos


def buscar_inteligente(
    session: Session,
    *,
    q: str,
    escopo: str = "todas",
    ordenar: str = "relevancia",
    data_inicio: date | None = None,
    data_fim: date | None = None,
    limite_por_categoria: int = 15,
) -> BuscaUnificadaRead:
    """Interpreta a consulta e pesquisa simultaneamente em notícias, artigos e dados oficiais."""
    garantir_serie_prodes_inicial(session)
    termo_limpo = (q or "").strip()
    escopo_norm = (escopo or "todas").strip().lower()
    ordenar_norm = (ordenar or "relevancia").strip().lower()

    stopwords = {
        "de",
        "da",
        "do",
        "das",
        "dos",
        "no",
        "na",
        "nos",
        "nas",
        "em",
        "para",
        "por",
        "com",
        "sobre",
        "ultimos",
        "últimos",
        "anos",
    }
    palavras = [
        p.lower()
        for p in termo_limpo.split()
        if len(p.strip()) >= 2 and p.lower() not in stopwords
    ]
    if not palavras and termo_limpo:
        palavras = [termo_limpo.lower()]

    # Expansão semântica PT -> EN para abranger também artigos internacionais
    sinonimos_en: list[str] = []
    mapa_pt_en = {
        "queimadas": "wildfire",
        "queimada": "fire",
        "incêndios": "wildfire",
        "incendios": "wildfire",
        "desmatamento": "deforestation",
        "amazônia": "amazon",
        "amazonia": "amazon",
        "pará": "para",
        "belém": "belem",
        "saúde": "health",
        "clima": "climate",
        "preservação": "conservation",
        "biodiversidade": "biodiversity",
    }
    for p in list(palavras):
        if p in mapa_pt_en and mapa_pt_en[p] not in palavras:
            sinonimos_en.append(mapa_pt_en[p])

    termos_consulta = palavras + sinonimos_en

    noticias_encontradas: list[Noticia] = []
    artigos_encontrados: list[ArtigoCientifico] = []
    dados_encontrados: list[DadoAmbientalOficial] = []
    itens_unificados: list[BuscaUnificadaItem] = []

    if escopo_norm in {"todas", "noticias"}:
        stmt_n = select(Noticia)
        if termos_consulta:
            clausulas_n = []
            for t in termos_consulta:
                like_t = f"%{t}%"
                clausulas_n.append(func.lower(Noticia.titulo).like(like_t))
                clausulas_n.append(func.lower(Noticia.descricao).like(like_t))
                clausulas_n.append(func.lower(Noticia.categoria).like(like_t))
            stmt_n = stmt_n.where(or_(*clausulas_n))
        if data_inicio:
            stmt_n = stmt_n.where(
                Noticia.data_publicacao
                >= datetime.combine(
                    data_inicio, datetime.min.time(), tzinfo=timezone.utc
                )
            )
        if data_fim:
            stmt_n = stmt_n.where(
                Noticia.data_publicacao
                <= datetime.combine(
                    data_fim, datetime.max.time(), tzinfo=timezone.utc
                )
            )
        noticias_encontradas = list(
            session.exec(
                stmt_n.order_by(col(Noticia.data_publicacao).desc()).limit(
                    limite_por_categoria
                )
            ).all()
        )
        for n in noticias_encontradas:
            rel = _calcular_relevancia(
                f"{n.titulo} {n.descricao} {n.categoria}", termos_consulta
            )
            itens_unificados.append(
                BuscaUnificadaItem(
                    tipo_fonte="noticia",
                    id=n.id or 0,
                    titulo=n.titulo,
                    resumo=n.descricao,
                    origem=n.origem_integracao,
                    instituicao_ou_veiculo=n.veiculo,
                    categoria=n.categoria,
                    data_referencia=(
                        n.data_publicacao.date().isoformat()
                        if n.data_publicacao
                        else None
                    ),
                    coletado_em=n.coletado_em,
                    url_original=n.url_original,
                    relevancia=rel,
                )
            )

    if escopo_norm in {"todas", "artigos"}:
        stmt_a = select(ArtigoCientifico)
        if termos_consulta:
            clausulas_a = []
            for t in termos_consulta:
                like_t = f"%{t}%"
                clausulas_a.append(
                    func.lower(ArtigoCientifico.titulo).like(like_t)
                )
                clausulas_a.append(
                    func.lower(ArtigoCientifico.resumo).like(like_t)
                )
                clausulas_a.append(
                    func.lower(ArtigoCientifico.palavras_chave).like(like_t)
                )
            stmt_a = stmt_a.where(or_(*clausulas_a))
        if data_inicio:
            stmt_a = stmt_a.where(
                ArtigoCientifico.ano_publicacao >= data_inicio.year
            )
        if data_fim:
            stmt_a = stmt_a.where(
                ArtigoCientifico.ano_publicacao <= data_fim.year
            )
        artigos_encontrados = list(
            session.exec(
                stmt_a.order_by(
                    col(ArtigoCientifico.ano_publicacao).desc(),
                    col(ArtigoCientifico.citacoes).desc(),
                ).limit(limite_por_categoria)
            ).all()
        )
        for a in artigos_encontrados:
            rel = _calcular_relevancia(
                f"{a.titulo} {a.resumo} {a.palavras_chave}", termos_consulta
            )
            itens_unificados.append(
                BuscaUnificadaItem(
                    tipo_fonte="artigo",
                    id=a.id or 0,
                    titulo=a.titulo,
                    resumo=a.resumo,
                    origem=a.base_origem,
                    instituicao_ou_veiculo=a.instituicao_ou_periodico,
                    categoria=a.categoria,
                    data_referencia=(
                        str(a.ano_publicacao) if a.ano_publicacao else None
                    ),
                    coletado_em=a.coletado_em,
                    url_original=a.url_original,
                    doi=a.doi,
                    relevancia=rel,
                )
            )

    if escopo_norm in {"todas", "dados_oficiais"}:
        stmt_d = select(DadoAmbientalOficial)
        if termos_consulta:
            clausulas_d = []
            for t in termos_consulta:
                like_t = f"%{t}%"
                clausulas_d.append(
                    func.lower(DadoAmbientalOficial.observacao).like(like_t)
                )
                clausulas_d.append(
                    func.lower(DadoAmbientalOficial.fonte).like(like_t)
                )
                clausulas_d.append(
                    func.lower(DadoAmbientalOficial.municipio).like(like_t)
                )
                clausulas_d.append(
                    func.lower(DadoAmbientalOficial.periodo_rotulo).like(like_t)
                )
                if t in {"pará", "para", "pa"}:
                    clausulas_d.append(DadoAmbientalOficial.estado == "PA")
                if t in {"queimadas", "queimada", "incêndios", "incendios", "focos"}:
                    clausulas_d.append(
                        DadoAmbientalOficial.tipo_metrica == "foco_de_calor"
                    )
                if t in {"desmatamento", "prodes", "deter", "alertas"}:
                    clausulas_d.append(
                        or_(
                            DadoAmbientalOficial.tipo_metrica
                            == "alerta_desmatamento",
                            DadoAmbientalOficial.tipo_metrica
                            == "desmatamento_consolidado",
                        )
                    )
            stmt_d = stmt_d.where(or_(*clausulas_d))
        if data_inicio:
            stmt_d = stmt_d.where(
                DadoAmbientalOficial.data_referencia >= data_inicio
            )
        if data_fim:
            stmt_d = stmt_d.where(
                DadoAmbientalOficial.data_referencia <= data_fim
            )
        dados_encontrados = list(
            session.exec(
                stmt_d.order_by(
                    col(DadoAmbientalOficial.data_referencia).desc()
                ).limit(limite_por_categoria)
            ).all()
        )
        for d in dados_encontrados:
            titulo_dado = (
                f"{d.fonte} — {d.municipio + '/' if d.municipio else ''}{d.estado} "
                f"({d.valor:g} {d.unidade})"
            )
            rel = _calcular_relevancia(
                f"{titulo_dado} {d.observacao or ''} {d.periodo_rotulo}",
                termos_consulta,
            )
            itens_unificados.append(
                BuscaUnificadaItem(
                    tipo_fonte="dado_oficial",
                    id=d.id or 0,
                    titulo=titulo_dado,
                    resumo=d.observacao or d.periodo_rotulo,
                    origem=d.fonte,
                    instituicao_ou_veiculo=d.instituicao,
                    categoria=d.tipo_metrica,
                    data_referencia=d.data_referencia.isoformat(),
                    coletado_em=d.coletado_em,
                    url_original=d.url_fonte,
                    relevancia=rel,
                )
            )

    if ordenar_norm == "data":
        itens_unificados.sort(
            key=lambda x: (x.data_referencia or "", x.relevancia), reverse=True
        )
    else:
        itens_unificados.sort(
            key=lambda x: (x.relevancia, x.data_referencia or ""), reverse=True
        )

    return BuscaUnificadaRead(
        termo=termo_limpo,
        escopo=escopo_norm,
        ordenacao=ordenar_norm,
        total=len(itens_unificados),
        total_noticias=len(noticias_encontradas),
        total_artigos=len(artigos_encontrados),
        total_dados_oficiais=len(dados_encontrados),
        noticias=[NoticiaRead.model_validate(n) for n in noticias_encontradas],
        artigos=[ArtigoRead.model_validate(a) for a in artigos_encontrados],
        dados_oficiais=[
            DadoAmbientalRead.model_validate(d) for d in dados_encontrados
        ],
        resultados=itens_unificados,
    )


def obter_painel_saude(session: Session) -> PainelSaudeRead:
    """Retorna o painel completo de saúde do sistema e das integrações externas."""
    status_integracoes = garantir_catalogo_integracoes(session)
    garantir_serie_prodes_inicial(session)

    total_users = int(session.exec(select(func.count(User.id))).one() or 0)
    total_ocorr = int(
        session.exec(select(func.count(Ocorrencia.id))).one() or 0
    )
    total_not = int(session.exec(select(func.count(Noticia.id))).one() or 0)
    total_art = int(
        session.exec(select(func.count(ArtigoCientifico.id))).one() or 0
    )
    total_amb = int(
        session.exec(select(func.count(DadoAmbientalOficial.id))).one() or 0
    )

    ult_not = session.exec(select(func.max(Noticia.coletado_em))).one()
    ult_art = session.exec(
        select(func.max(ArtigoCientifico.coletado_em))
    ).one()
    ult_mon = session.exec(
        select(func.max(DadoAmbientalOficial.coletado_em))
    ).one()

    return PainelSaudeRead(
        status_backend="online",
        status_banco="online",
        total_usuarios=total_users,
        total_ocorrencias=total_ocorr,
        total_noticias=total_not,
        total_artigos=total_art,
        total_dados_ambientais=total_amb,
        ultima_atualizacao_noticias=ult_not,
        ultima_atualizacao_artigos=ult_art,
        ultima_atualizacao_monitoramento=ult_mon,
        integracoes=[
            IntegracaoStatusRead.model_validate(i) for i in status_integracoes
        ],
        fontes_documentadas_limitacoes=FONTES_LIMITACOES_DOCUMENTADAS,
        verificado_em=datetime.now(timezone.utc),
    )
