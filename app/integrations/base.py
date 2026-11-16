import html
import ipaddress
import re
import socket
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

import requests

from app.core.config import settings

_TAG_RE = re.compile(r"<[^>]+>")
_WS_RE = re.compile(r"\s+")
_TRACKING_PARAMS = {
    "utm_source",
    "utm_medium",
    "utm_campaign",
    "utm_term",
    "utm_content",
    "fbclid",
    "gclid",
    "mc_cid",
    "mc_eid",
    "ref",
}

ESTADOS_AMAZONIA_LEGAL = {
    "AC",
    "AP",
    "AM",
    "MA",
    "MT",
    "PA",
    "RO",
    "RR",
    "TO",
}

MAPA_NOME_PARA_UF = {
    "ACRE": "AC",
    "AMAPA": "AP",
    "AMAPÁ": "AP",
    "AMAZONAS": "AM",
    "MARANHAO": "MA",
    "MARANHÃO": "MA",
    "MATO GROSSO": "MT",
    "PARA": "PA",
    "PARÁ": "PA",
    "RONDONIA": "RO",
    "RONDÔNIA": "RO",
    "RORAIMA": "RR",
    "TOCANTINS": "TO",
    "DISTRITO FEDERAL": "DF",
    "GOIAS": "GO",
    "GOIÁS": "GO",
    "MATO GROSSO DO SUL": "MS",
    "MINAS GERAIS": "MG",
    "SAO PAULO": "SP",
    "SÃO PAULO": "SP",
    "BAHIA": "BA",
    "PIAUI": "PI",
    "PIAUÍ": "PI",
    "CEARA": "CE",
    "CEARÁ": "CE",
    "PERNAMBUCO": "PE",
    "PARANA": "PR",
    "PARANÁ": "PR",
    "RIO DE JANEIRO": "RJ",
    "RIO GRANDE DO SUL": "RS",
    "SANTA CATARINA": "SC",
    "ESPIRITO SANTO": "ES",
    "ESPÍRITO SANTO": "ES",
    "RIO GRANDE DO NORTE": "RN",
    "PARAIBA": "PB",
    "PARAÍBA": "PB",
    "ALAGOAS": "AL",
    "SERGIPE": "SE",
}


class IntegrationError(RuntimeError):
    """Erro controlado de comunicação ou formato em integração externa."""


def user_agent() -> str:
    email = settings.CENTRAL_CONTACT_EMAIL or "contato@ecomonitor.local"
    return f"EcoMonitor/1.0 (+https://ecomonitor.local; mailto:{email})"


def validar_url_externa(url: str) -> str:
    """Garante que a URL usa http/https e não aponta para rede local/privada."""
    texto = (url or "").strip()
    parsed = urlparse(texto)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise IntegrationError(f"URL externa inválida: {texto!r}")

    hostname = (parsed.hostname or "").lower()
    if hostname in {"localhost", "127.0.0.1", "0.0.0.0", "::1"}:
        raise IntegrationError("URL aponta para host local bloqueado.")

    try:
        ip = ipaddress.ip_address(hostname)
        if ip.is_private or ip.is_loopback or ip.is_link_local:
            raise IntegrationError("URL aponta para IP privado bloqueado.")
    except ValueError:
        pass

    return texto


def normalizar_url(url: str) -> str:
    """Remove parâmetros de rastreamento e fragmentos para deduplicação."""
    texto = (url or "").strip()
    if not texto:
        return ""
    parsed = urlparse(texto)
    scheme = (parsed.scheme or "https").lower()
    netloc = parsed.netloc.lower()
    path = parsed.path.rstrip("/") or "/"
    query_pairs = [
        (k, v)
        for k, v in parse_qsl(parsed.query, keep_blank_values=False)
        if k.lower() not in _TRACKING_PARAMS
    ]
    query_pairs.sort()
    return urlunparse((scheme, netloc, path, "", urlencode(query_pairs), ""))


def normalizar_doi(doi: str | None) -> str | None:
    """Normaliza um identificador DOI removendo prefixos de URL."""
    if not doi:
        return None
    limpo = doi.strip().lower()
    for prefixo in (
        "https://doi.org/",
        "http://doi.org/",
        "https://dx.doi.org/",
        "doi:",
    ):
        if limpo.startswith(prefixo):
            limpo = limpo[len(prefixo) :]
    limpo = limpo.strip()
    return limpo or None


def limpar_texto_externo(texto: str | None, limite: int = 600) -> str:
    """Remove tags HTML, decodifica entidades e limita o comprimento."""
    if not texto:
        return ""
    sem_tags = _TAG_RE.sub(" ", str(texto))
    decodificado = html.unescape(sem_tags)
    compacto = _WS_RE.sub(" ", decodificado).strip()
    if len(compacto) > limite:
        return compacto[: limite - 1].rstrip() + "…"
    return compacto


def classificar_categoria_noticia(
    titulo: str, descricao: str = "", padrao: str = "preservacao"
) -> str:
    """Classifica uma notícia em uma das categorias temáticas da Central."""
    base = f"{titulo} {descricao}".lower()

    if any(
        termo in base
        for termo in (
            "pará",
            "belem",
            "belém",
            "santarém",
            "santarem",
            "altamira",
            "marabá",
            "maraba",
            "xingu",
            "tapajós",
            "tapajos",
            "itaituba",
            "novo progresso",
            "são félix do xingu",
        )
    ):
        return "para"

    if any(
        termo in base
        for termo in (
            "queimada",
            "incêndio",
            "incendio",
            "foco de calor",
            "focos de calor",
            "fumaça",
            "wildfire",
            "fire",
        )
    ):
        return "queimadas"

    if any(
        termo in base
        for termo in (
            "desmatamento",
            "desflorestamento",
            "deter",
            "prodes",
            "degradação",
            "degradacao",
            "garimpo",
            "deforestation",
            "logging",
        )
    ):
        return "desmatamento"

    if any(
        termo in base
        for termo in (
            "ibama",
            "icmbio",
            "fiscalização",
            "fiscalizacao",
            "multa",
            "embargo",
            "operação",
            "operacao",
            "polícia federal",
        )
    ):
        return "fiscalizacao"

    if any(
        termo in base
        for termo in (
            "amazônia",
            "amazonia",
            "amazon",
            "floresta amazônica",
        )
    ):
        return "amazonia"

    if any(
        termo in base
        for termo in (
            "clima",
            "climática",
            "climatica",
            "aquecimento global",
            "efeito estufa",
            "carbono",
            "climate",
            "cop30",
            "seca",
            "estiagem",
        )
    ):
        return "clima"

    return padrao if padrao else "preservacao"


_RELEVANCIA_AMBIENTAL_RE = re.compile(
    r"\b("
    r"amaz[ôo]nia|amaz[ôo]nica|queimada|queimadas|inc[êe]ndio|inc[êe]ndios|"
    r"desmatamento|desflorestamento|floresta|florestal|ambiental|ambientais|"
    r"meio\s+ambiente|clima|clim[áa]tica|clim[áa]ticas|biodiversidade|"
    r"ibama|icmbio|inpe|prodes|deter|garimpo|conserva[çc][ãa]o|preserva[çc][ãa]o|"
    r"estiagem|bioma|pantanal|cerrado|caatinga|mata\s+atl[âa]ntica|"
    r"cop30|cop31|foco\s+de\s+calor|focos\s+de\s+calor|reflorestamento"
    r")\b",
    re.IGNORECASE,
)


def tem_relevancia_ambiental(titulo: str, descricao: str = "") -> bool:
    """Verifica por palavra inteira se uma notícia de feed geral possui temática ambiental."""
    base = f"{titulo} {descricao}"
    return bool(_RELEVANCIA_AMBIENTAL_RE.search(base))


def classificar_categoria_artigo(titulo: str, resumo: str = "") -> str:
    """Classifica um artigo científico para os filtros da biblioteca."""
    base = f"{titulo} {resumo}".lower()
    if any(
        t in base
        for t in ("fire", "wildfire", "burned", "queimada", "incêndio", "fogo")
    ):
        return "queimadas"
    if any(
        t in base
        for t in (
            "deforestation",
            "desmatamento",
            "prodes",
            "deter",
            "land use",
            "forest loss",
            "degradation",
        )
    ):
        return "desmatamento"
    if any(
        t in base
        for t in (
            "biodiversity",
            "biodiversidade",
            "species",
            "espécies",
            "fauna",
            "flora",
            "conservation",
        )
    ):
        return "biodiversidade"
    if any(
        t in base
        for t in (
            "climate",
            "climática",
            "carbon",
            "carbono",
            "warming",
            "drought",
            "seca",
        )
    ):
        return "clima"
    return "amazonia"


def requisitar_http(
    url: str,
    *,
    params: dict | None = None,
    headers: dict[str, str] | None = None,
    timeout: int | None = None,
) -> requests.Response:
    """Executa GET HTTP com timeout, User-Agent institucional e validação."""
    validar_url_externa(url)
    cabecalhos = {"User-Agent": user_agent(), "Accept": "*/*"}
    if headers:
        cabecalhos.update(headers)
    tempo = timeout or max(int(settings.CENTRAL_HTTP_TIMEOUT), 5)

    try:
        resposta = requests.get(
            url, params=params, headers=cabecalhos, timeout=tempo
        )
    except (requests.RequestException, socket.error) as exc:
        raise IntegrationError(
            f"Falha de conexão ao consultar {url}: {exc}"
        ) from exc

    if resposta.status_code == 429:
        raise IntegrationError(
            f"Limite de requisições (HTTP 429) atingido em {url}."
        )
    if resposta.status_code >= 400:
        raise IntegrationError(
            f"Resposta HTTP {resposta.status_code} ao consultar {url}."
        )

    return resposta
