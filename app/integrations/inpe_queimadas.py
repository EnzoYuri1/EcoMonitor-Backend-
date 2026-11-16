from collections import defaultdict
import csv
from datetime import date, datetime
import io
import re

from app.integrations.base import (
    ESTADOS_AMAZONIA_LEGAL,
    MAPA_NOME_PARA_UF,
    IntegrationError,
    requisitar_http,
)

INPE_DIARIO_DIR_URL = (
    "https://dataserver-coids.inpe.br/queimadas/queimadas/focos/csv/diario/Brasil/"
)
_ARQUIVO_CSV_RE = re.compile(r"focos_diario_br_(\d{8})\.csv")


def normalizar_uf_inpe(nome_estado: str) -> str:
    texto = (nome_estado or "").strip().upper()
    if len(texto) == 2 and texto.isalpha():
        return texto
    return MAPA_NOME_PARA_UF.get(texto, "PA" if "PAR" in texto else "BR")


def descobrir_ultimo_csv_diario(html_indice: str) -> tuple[str, date]:
    """Localiza o nome e a data do último CSV diário na listagem do INPE."""
    encontrados = _ARQUIVO_CSV_RE.findall(html_indice or "")
    if not encontrados:
        raise IntegrationError(
            "Nenhum arquivo focos_diario_br_AAAAMMDD.csv encontrado no INPE."
        )
    datas_unicas = sorted(set(encontrados))
    ultimo = datas_unicas[-1]
    data_ref = datetime.strptime(ultimo, "%Y%m%d").date()
    return f"focos_diario_br_{ultimo}.csv", data_ref


def parsear_csv_focos_inpe(
    csv_texto: str, data_ref: date, url_fonte: str
) -> list[dict]:
    """Agrega os focos de calor do CSV diário do INPE por UF e destaca municípios do Pará."""
    if not csv_texto or not csv_texto.strip():
        return []

    leitor = csv.DictReader(io.StringIO(csv_texto))
    por_uf: dict[str, int] = defaultdict(int)
    por_municipio_pa: dict[str, tuple[int, float | None, float | None]] = {}

    for linha in leitor:
        if not isinstance(linha, dict):
            continue
        uf = normalizar_uf_inpe(linha.get("estado", ""))
        if len(uf) != 2 or uf == "BR":
            continue
        por_uf[uf] += 1

        if uf == "PA":
            mun = (linha.get("municipio") or "").strip().title()
            if mun:
                atual, lat_ant, lon_ant = por_municipio_pa.get(
                    mun, (0, None, None)
                )
                try:
                    lat = float((linha.get("lat") or "").strip())
                    lon = float((linha.get("lon") or "").strip())
                except ValueError:
                    lat, lon = lat_ant, lon_ant
                por_municipio_pa[mun] = (atual + 1, lat, lon)

    registros: list[dict] = []
    data_iso = data_ref.isoformat()
    rotulo_dia = data_ref.strftime("%d/%m/%Y")

    for uf, total in sorted(por_uf.items()):
        amz = uf in ESTADOS_AMAZONIA_LEGAL
        registros.append(
            {
                "tipo_metrica": "foco_de_calor",
                "fonte": "INPE — Programa Queimadas (BDQueimadas)",
                "instituicao": "INPE / MCTI",
                "identificador_original": f"inpe_focos_uf:{data_iso}:{uf}",
                "estado": uf,
                "municipio": None,
                "bioma": "Amazônia" if amz else "Brasil",
                "amazonia_legal": amz,
                "latitude": None,
                "longitude": None,
                "data_referencia": data_ref,
                "periodo_rotulo": f"Consolidado diário ({rotulo_dia})",
                "valor": float(total),
                "unidade": "focos",
                "satelite_ou_metodo": "Multissatélite (CSV diário INPE)",
                "nivel_confianca": "oficial",
                "url_fonte": url_fonte,
                "observacao": (
                    f"Total de {total} focos de calor detectados na UF {uf} "
                    f"no arquivo diário oficial do INPE ({rotulo_dia})."
                ),
            }
        )

    # Top 8 municípios do Pará com mais focos no dia
    top_pa = sorted(
        por_municipio_pa.items(), key=lambda par: par[1][0], reverse=True
    )[:8]
    for mun, (qtd, lat, lon) in top_pa:
        mun_slug = re.sub(r"[^a-z0-9]+", "_", mun.lower()).strip("_")
        registros.append(
            {
                "tipo_metrica": "foco_de_calor",
                "fonte": "INPE — Programa Queimadas (Municípios do Pará)",
                "instituicao": "INPE / MCTI",
                "identificador_original": f"inpe_focos_pa_mun:{data_iso}:{mun_slug}",
                "estado": "PA",
                "municipio": mun,
                "bioma": "Amazônia",
                "amazonia_legal": True,
                "latitude": lat,
                "longitude": lon,
                "data_referencia": data_ref,
                "periodo_rotulo": f"Município PA ({rotulo_dia})",
                "valor": float(qtd),
                "unidade": "focos",
                "satelite_ou_metodo": "Multissatélite (CSV diário INPE)",
                "nivel_confianca": "oficial",
                "url_fonte": url_fonte,
                "observacao": (
                    f"{qtd} focos de calor registrados em {mun}/PA no "
                    f"consolidado diário do INPE."
                ),
            }
        )

    return registros


def coletar_focos_inpe_diario() -> list[dict]:
    """Consulta o servidor de dados abertos do INPE e agrega o último CSV diário."""
    indice_resp = requisitar_http(INPE_DIARIO_DIR_URL)
    nome_arquivo, data_ref = descobrir_ultimo_csv_diario(indice_resp.text)
    url_csv = f"{INPE_DIARIO_DIR_URL}{nome_arquivo}"
    csv_resp = requisitar_http(url_csv, timeout=25)
    # O CSV do INPE é codificado em UTF-8
    texto = csv_resp.content.decode("utf-8", errors="replace")
    return parsear_csv_focos_inpe(texto, data_ref, url_csv)
