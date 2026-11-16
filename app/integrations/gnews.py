from datetime import datetime, timezone

from app.core.config import settings
from app.integrations.base import (
    IntegrationError,
    classificar_categoria_noticia,
    limpar_texto_externo,
    normalizar_url,
    requisitar_http,
)

GNEWS_ENDPOINT = "https://gnews.io/api/v4/search"

CONSULTAS_PADRAO_GNEWS = [
    ("queimadas Amazônia OR incêndio florestal Pará", "queimadas"),
    ("desmatamento Amazônia OR desmatamento Pará", "desmatamento"),
]


def gnews_configurada() -> bool:
    return bool((settings.GNEWS_API_KEY or "").strip())


def _parse_data_iso(valor: str | None) -> datetime | None:
    if not valor:
        return None
    try:
        texto = valor.strip().replace("Z", "+00:00")
        dt = datetime.fromisoformat(texto)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except ValueError:
        return None


def parsear_resposta_gnews(
    payload: dict, categoria_padrao: str = "amazonia"
) -> list[dict]:
    """Converte o JSON da GNews API v4 em registros normalizados de notícias."""
    artigos = payload.get("articles") or []
    itens: list[dict] = []

    for art in artigos:
        if not isinstance(art, dict):
            continue
        titulo = limpar_texto_externo(art.get("title"), limite=300)
        descricao = limpar_texto_externo(art.get("description"), limite=360)
        url = (art.get("url") or "").strip()
        url_norm = normalizar_url(url)
        if not titulo or not url_norm:
            continue

        fonte_obj = art.get("source") or {}
        veiculo = (
            limpar_texto_externo(fonte_obj.get("name"), limite=140)
            if isinstance(fonte_obj, dict)
            else "GNews"
        ) or "GNews"

        imagem = (art.get("image") or "").strip() or None
        categoria = classificar_categoria_noticia(
            titulo, descricao, padrao=categoria_padrao
        )

        itens.append(
            {
                "titulo": titulo,
                "descricao": descricao,
                "imagem_url": imagem,
                "veiculo": veiculo,
                "origem_integracao": "gnews_api",
                "url_original": url,
                "url_normalizada": url_norm,
                "data_publicacao": _parse_data_iso(art.get("publishedAt")),
                "categoria": categoria,
                "idioma": "pt",
            }
        )

    return itens


def coletar_noticias_gnews(max_por_consulta: int = 10) -> list[dict]:
    """Busca notícias em português na GNews API v4 quando a chave está ativa."""
    chave = (settings.GNEWS_API_KEY or "").strip()
    if not chave:
        raise IntegrationError(
            "GNEWS_API_KEY não configurada. Integração opcional inativa."
        )

    acumulado: list[dict] = []
    for query, cat_padrao in CONSULTAS_PADRAO_GNEWS:
        resposta = requisitar_http(
            GNEWS_ENDPOINT,
            params={
                "q": query,
                "lang": "pt",
                "country": "br",
                "max": min(max(max_por_consulta, 1), 10),
                "sortby": "publishedAt",
                "apikey": chave,
            },
        )
        dados = resposta.json()
        acumulado.extend(
            parsear_resposta_gnews(dados, categoria_padrao=cat_padrao)
        )

    return acumulado
