from app.core.config import settings
from app.integrations.base import (
    classificar_categoria_artigo,
    limpar_texto_externo,
    normalizar_doi,
    requisitar_http,
)

OPENALEX_WORKS_URL = "https://api.openalex.org/works"
CROSSREF_WORKS_URL = "https://api.crossref.org/works"

CONSULTAS_CIENTIFICAS_INICIAIS = [
    ("Amazon wildfire burned area Pará Brazil", "queimadas"),
    ("Amazon deforestation PRODES DETER Pará", "desmatamento"),
    ("Amazonia biodiversity conservation forest recovery", "biodiversidade"),
    ("Amazon climate change drought carbon emissions", "clima"),
]


def _reconstruir_resumo_invertido(indice_invertido: dict | None) -> str:
    """Reconstrói o abstract do formato abstract_inverted_index do OpenAlex."""
    if not isinstance(indice_invertido, dict) or not indice_invertido:
        return ""
    posicoes: list[tuple[int, str]] = []
    for palavra, indices in indice_invertido.items():
        if not isinstance(indices, list):
            continue
        for pos in indices:
            if isinstance(pos, int):
                posicoes.append((pos, str(palavra)))
    if not posicoes:
        return ""
    posicoes.sort(key=lambda par: par[0])
    texto = " ".join(p for _, p in posicoes)
    return limpar_texto_externo(texto, limite=1800)


def parsear_obra_openalex(
    item: dict, categoria_padrao: str = "amazonia"
) -> dict | None:
    """Converte um registro de work do OpenAlex em dicionário padronizado."""
    if not isinstance(item, dict):
        return None

    titulo = limpar_texto_externo(
        item.get("display_name") or item.get("title"), limite=500
    )
    if not titulo:
        return None

    doi = normalizar_doi(item.get("doi"))
    openalex_id = (item.get("id") or "").strip()
    identificador = f"doi:{doi}" if doi else f"openalex:{openalex_id or titulo.lower()[:120]}"

    autores_lista: list[str] = []
    instituicoes_lista: list[str] = []
    pesquisa_br = False

    for aut in (item.get("authorships") or [])[:8]:
        if not isinstance(aut, dict):
            continue
        autor_obj = aut.get("author") or {}
        nome_autor = limpar_texto_externo(
            autor_obj.get("display_name"), limite=100
        )
        if nome_autor:
            autores_lista.append(nome_autor)

        paises = aut.get("countries") or []
        if "BR" in paises:
            pesquisa_br = True

        for inst in (aut.get("institutions") or [])[:2]:
            if isinstance(inst, dict):
                if inst.get("country_code") == "BR":
                    pesquisa_br = True
                nome_inst = limpar_texto_externo(
                    inst.get("display_name"), limite=140
                )
                if nome_inst and nome_inst not in instituicoes_lista:
                    instituicoes_lista.append(nome_inst)

    loc_primaria = item.get("primary_location") or {}
    fonte_obj = (
        loc_primaria.get("source") if isinstance(loc_primaria, dict) else {}
    ) or {}
    periodico = limpar_texto_externo(fonte_obj.get("display_name"), limite=200)
    if not periodico and instituicoes_lista:
        periodico = instituicoes_lista[0]
    if not periodico:
        periodico = "Periódico científico indexado (OpenAlex)"

    indexed_in = item.get("indexed_in") or []
    base_origem = "OpenAlex / SciELO" if "scielo" in indexed_in else "OpenAlex"
    if "scielo" in indexed_in:
        pesquisa_br = True

    resumo = _reconstruir_resumo_invertido(item.get("abstract_inverted_index"))
    if not resumo:
        resumo = (
            "Resumo integral não disponibilizado pela editora na base aberta; "
            "acesse o link original ou DOI para o texto completo."
        )

    conceitos: list[str] = []
    for topico in (item.get("topics") or item.get("concepts") or [])[:6]:
        if isinstance(topico, dict):
            nome_topico = limpar_texto_externo(
                topico.get("display_name"), limite=60
            )
            if nome_topico:
                conceitos.append(nome_topico)

    ano = item.get("publication_year")
    ano_int = int(ano) if isinstance(ano, int) and 1900 <= ano <= 2100 else None

    url_original = (
        (f"https://doi.org/{doi}" if doi else "")
        or (loc_primaria.get("landing_page_url") if isinstance(loc_primaria, dict) else "")
        or openalex_id
    )
    if not url_original:
        return None

    categoria = classificar_categoria_artigo(titulo, resumo) or categoria_padrao
    citacoes = int(item.get("cited_by_count") or 0)

    return {
        "titulo": titulo,
        "autores": ", ".join(autores_lista) or "Autores não informados na base",
        "instituicao_ou_periodico": periodico,
        "ano_publicacao": ano_int,
        "resumo": resumo,
        "palavras_chave": ", ".join(conceitos) or categoria,
        "doi": doi,
        "identificador_unico": identificador,
        "url_original": str(url_original).strip(),
        "base_origem": base_origem,
        "categoria": categoria,
        "citacoes": max(citacoes, 0),
        "pesquisa_brasileira": pesquisa_br,
    }


def coletar_artigos_openalex(por_consulta: int = 8) -> list[dict]:
    """Consulta a API do OpenAlex para os temas prioritários da Amazônia."""
    resultados: list[dict] = []
    email = settings.CENTRAL_CONTACT_EMAIL or "contato@ecomonitor.local"
    chave = (settings.OPENALEX_API_KEY or "").strip()

    for query, cat_padrao in CONSULTAS_CIENTIFICAS_INICIAIS:
        params: dict[str, str | int] = {
            "search": query,
            "per-page": min(max(por_consulta, 1), 25),
            "mailto": email,
        }
        if chave:
            params["api_key"] = chave

        resposta = requisitar_http(OPENALEX_WORKS_URL, params=params)
        dados = resposta.json()
        for item in dados.get("results") or []:
            convertido = parsear_obra_openalex(item, categoria_padrao=cat_padrao)
            if convertido:
                resultados.append(convertido)

    return resultados


def parsear_obra_crossref(
    item: dict, categoria_padrao: str = "amazonia"
) -> dict | None:
    """Converte um item da API REST do Crossref em dicionário padronizado."""
    if not isinstance(item, dict):
        return None

    titulos = item.get("title") or []
    titulo_bruto = titulos[0] if isinstance(titulos, list) and titulos else ""
    titulo = limpar_texto_externo(titulo_bruto, limite=500)
    doi = normalizar_doi(item.get("DOI"))
    if not titulo or not doi:
        return None

    autores_lista: list[str] = []
    for aut in (item.get("author") or [])[:8]:
        if isinstance(aut, dict):
            nome = f"{aut.get('given', '')} {aut.get('family', '')}".strip()
            if nome:
                autores_lista.append(limpar_texto_externo(nome, limite=100))

    periodicos = item.get("container-title") or []
    periodico = (
        limpar_texto_externo(periodicos[0], limite=200)
        if isinstance(periodicos, list) and periodicos
        else "Periódico científico (Crossref)"
    )

    ano_int: int | None = None
    for campo_data in ("published-print", "published-online", "issued", "created"):
        bloco = item.get(campo_data)
        if isinstance(bloco, dict):
            partes = bloco.get("date-parts")
            if (
                isinstance(partes, list)
                and partes
                and isinstance(partes[0], list)
                and partes[0]
            ):
                possivel_ano = partes[0][0]
                if isinstance(possivel_ano, int) and 1900 <= possivel_ano <= 2100:
                    ano_int = possivel_ano
                    break

    resumo = limpar_texto_externo(item.get("abstract"), limite=1800)
    if not resumo:
        resumo = (
            "Metadados verificados via Crossref. Resumo integral não "
            "disponibilizado no registro aberto; consulte o DOI."
        )

    assuntos = [
        limpar_texto_externo(s, limite=60)
        for s in (item.get("subject") or [])[:6]
        if isinstance(s, str)
    ]
    categoria = classificar_categoria_artigo(titulo, resumo) or categoria_padrao
    citacoes = int(item.get("is-referenced-by-count") or 0)
    texto_busca_br = f"{titulo} {periodico}".lower()
    pesquisa_br = any(
        t in texto_busca_br for t in ("brasil", "brazil", "pará", "amazonia", "amazônia", "inpe")
    )

    return {
        "titulo": titulo,
        "autores": ", ".join(autores_lista) or "Autores registrados no DOI",
        "instituicao_ou_periodico": periodico,
        "ano_publicacao": ano_int,
        "resumo": resumo,
        "palavras_chave": ", ".join(assuntos) or categoria,
        "doi": doi,
        "identificador_unico": f"doi:{doi}",
        "url_original": f"https://doi.org/{doi}",
        "base_origem": "Crossref",
        "categoria": categoria,
        "citacoes": max(citacoes, 0),
        "pesquisa_brasileira": pesquisa_br,
    }


def coletar_artigos_crossref(linhas: int = 8) -> list[dict]:
    """Consulta metadados de publicações científicas na API do Crossref."""
    email = settings.CENTRAL_CONTACT_EMAIL or "contato@ecomonitor.local"
    resposta = requisitar_http(
        CROSSREF_WORKS_URL,
        params={
            "query": "Amazonia deforestation wildfire Pará Brazil",
            "rows": min(max(linhas, 1), 20),
            "mailto": email,
        },
    )
    dados = resposta.json()
    mensagem = dados.get("message") or {}
    itens = mensagem.get("items") or []
    saida: list[dict] = []
    for item in itens:
        conv = parsear_obra_crossref(item)
        if conv:
            saida.append(conv)
    return saida
