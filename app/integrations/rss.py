from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
import json
from pathlib import Path
import re
import xml.etree.ElementTree as ET

from app.core.config import BASE_DIR
from app.integrations.base import (
    IntegrationError,
    classificar_categoria_noticia,
    limpar_texto_externo,
    normalizar_url,
    requisitar_http,
    tem_relevancia_ambiental,
)

_IMG_SRC_RE = re.compile(r'<img[^>]+src=["\']([^"\']+)["\']', re.IGNORECASE)
_DOCTYPE_ENTITY_RE = re.compile(r"<!ENTITY\b", re.IGNORECASE)
_BARE_AMP_RE = re.compile(
    r"&(?!(?:[a-zA-Z][a-zA-Z0-9]*|#\d+|#x[0-9a-fA-F]+);)"
)


def carregar_fontes_rss(caminho: Path | None = None) -> list[dict]:
    """Carrega a lista configurável de feeds RSS a partir de config/fontes_rss.json."""
    arquivo = caminho or (BASE_DIR / "config" / "fontes_rss.json")
    if not arquivo.exists():
        return []
    dados = json.loads(arquivo.read_text(encoding="utf-8"))
    return [f for f in dados if isinstance(f, dict) and f.get("ativo", True)]


def _parse_data_rss(valor: str | None) -> datetime | None:
    if not valor:
        return None
    texto = valor.strip()
    try:
        dt = parsedate_to_datetime(texto)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except (TypeError, ValueError):
        pass

    for fmt in (
        "%Y-%m-%dT%H:%M:%S%z",
        "%Y-%m-%dT%H:%M:%SZ",
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d",
    ):
        try:
            dt = datetime.strptime(texto[:25], fmt)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt.astimezone(timezone.utc)
        except ValueError:
            continue
    return None


def _extrair_imagem(item: ET.Element, descricao_bruta: str) -> str | None:
    for elem in item.iter():
        tag_local = elem.tag.split("}")[-1].lower()
        if tag_local in {"content", "thumbnail", "enclosure"}:
            url = elem.attrib.get("url") or elem.attrib.get("href")
            tipo = (elem.attrib.get("type") or "").lower()
            if url and (
                not tipo
                or "image" in tipo
                or url.lower().endswith((".jpg", ".jpeg", ".png", ".webp"))
            ):
                return url.strip()

    match = _IMG_SRC_RE.search(descricao_bruta or "")
    if match:
        return match.group(1).strip()
    return None


def _texto_filho(elem: ET.Element, nomes: tuple[str, ...]) -> str:
    for filho in elem:
        tag_local = filho.tag.split("}")[-1].lower()
        if tag_local in nomes and (filho.text or "").strip():
            return filho.text.strip()
    return ""


def parsear_xml_rss(
    xml_texto: str,
    *,
    veiculo: str,
    origem_id: str,
    idioma: str = "pt",
    categoria_padrao: str = "preservacao",
    filtrar_ambiental: bool = False,
    limite: int = 25,
) -> list[dict]:
    """Converte um XML RSS/Atom em dicionários prontos para persistência."""
    if not xml_texto or not xml_texto.strip():
        return []
    if _DOCTYPE_ENTITY_RE.search(xml_texto):
        raise IntegrationError(
            "XML RSS rejeitado por conter declarações ENTITY."
        )

    try:
        xml_limpo = _BARE_AMP_RE.sub("&amp;", xml_texto.strip())
        raiz = ET.fromstring(xml_limpo)
    except ET.ParseError as exc:
        raise IntegrationError(f"XML RSS inválido em {veiculo}: {exc}") from exc

    itens_xml: list[ET.Element] = []
    for elem in raiz.iter():
        tag_local = elem.tag.split("}")[-1].lower()
        if tag_local in {"item", "entry"}:
            itens_xml.append(elem)

    resultados: list[dict] = []
    for item in itens_xml[:limite]:
        titulo_bruto = _texto_filho(item, ("title",))
        link = _texto_filho(item, ("link", "guid"))
        if not link:
            for filho in item:
                if filho.tag.split("}")[-1].lower() == "link":
                    href = filho.attrib.get("href")
                    if href:
                        link = href.strip()
                        break

        descricao_bruta = _texto_filho(
            item, ("description", "summary", "encoded", "content")
        )
        data_str = _texto_filho(
            item, ("pubdate", "published", "updated", "date")
        )

        titulo = limpar_texto_externo(titulo_bruto, limite=300)
        descricao = limpar_texto_externo(descricao_bruta, limite=360)
        url_norm = normalizar_url(link)

        if not titulo or not url_norm:
            continue

        if filtrar_ambiental and not tem_relevancia_ambiental(titulo, descricao):
            continue

        imagem = _extrair_imagem(item, descricao_bruta)
        categoria = classificar_categoria_noticia(
            titulo, descricao, padrao=categoria_padrao
        )

        resultados.append(
            {
                "titulo": titulo,
                "descricao": descricao,
                "imagem_url": imagem,
                "veiculo": veiculo,
                "origem_integracao": f"rss:{origem_id}",
                "url_original": link.strip(),
                "url_normalizada": url_norm,
                "data_publicacao": _parse_data_rss(data_str),
                "categoria": categoria,
                "idioma": idioma,
            }
        )

    return resultados


def coletar_feed_rss(fonte: dict, limite: int = 20) -> list[dict]:
    """Faz download e parse de um único feed RSS configurado."""
    url = fonte.get("url", "")
    nome = fonte.get("nome", "Fonte RSS")
    origem_id = fonte.get("id", "rss")
    idioma = fonte.get("idioma", "pt")
    categoria_padrao = fonte.get("categoria_padrao", "preservacao")
    filtrar = bool(fonte.get("filtrar_ambiental", False))

    resposta = requisitar_http(url)
    # Decodifica respeitando o encoding do feed (ex.: ISO-8859-1 na Folha)
    conteudo = resposta.text
    return parsear_xml_rss(
        conteudo,
        veiculo=nome,
        origem_id=origem_id,
        idioma=idioma,
        categoria_padrao=categoria_padrao,
        filtrar_ambiental=filtrar,
        limite=limite,
    )
