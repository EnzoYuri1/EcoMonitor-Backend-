from collections import defaultdict
from datetime import date, datetime
import re

from app.integrations.base import ESTADOS_AMAZONIA_LEGAL, requisitar_http

DETER_WFS_URL = "https://terrabrasilis.dpi.inpe.br/geoserver/deter-amz/wfs"
PRODES_WFS_URL = (
    "https://terrabrasilis.dpi.inpe.br/geoserver/prodes-legal-amz/wfs"
)
TERRABRASILIS_PORTAL_URL = "https://terrabrasilis.dpi.inpe.br/"

# Série histórica oficial consolidada do PRODES Amazônia Legal (INPE/MCTI, km²)
# e participação do Estado do Pará, preservada como referência histórica
# verificável e complementada pelos registros do WFS do TerraBrasilis.
SERIE_HISTORICA_OFICIAL_PRODES = [
    {"ano": 2019, "amazonia_legal_km2": 10129.0, "para_km2": 4172.0},
    {"ano": 2020, "amazonia_legal_km2": 10851.0, "para_km2": 4899.0},
    {"ano": 2021, "amazonia_legal_km2": 13038.0, "para_km2": 5238.0},
    {"ano": 2022, "amazonia_legal_km2": 11594.0, "para_km2": 4141.0},
    {"ano": 2023, "amazonia_legal_km2": 9064.0, "para_km2": 3272.0},
    {"ano": 2024, "amazonia_legal_km2": 6288.0, "para_km2": 2362.0},
]


def _parse_float_br(valor: str | float | int | None) -> float:
    if valor is None:
        return 0.0
    if isinstance(valor, (int, float)):
        return float(valor)
    limpo = str(valor).strip().replace(",", ".")
    try:
        return float(limpo)
    except ValueError:
        return 0.0


def _parse_data_iso(valor: str | None) -> date:
    if not valor:
        return date.today()
    try:
        return datetime.strptime(str(valor).strip()[:10], "%Y-%m-%d").date()
    except ValueError:
        return date.today()


def parsear_geojson_deter(payload: dict) -> list[dict]:
    """Processa feições GeoJSON do DETER Amazônia Legal (alertas, km²)."""
    features = payload.get("features") or []
    por_uf: dict[str, float] = defaultdict(float)
    data_mais_recente = date(2024, 1, 1)
    detalhes_pa: list[dict] = []

    for feat in features:
        if not isinstance(feat, dict):
            continue
        props = feat.get("properties") or {}
        uf = str(props.get("uf") or "").strip().upper()
        if len(uf) != 2:
            continue
        area_km2 = _parse_float_br(props.get("areamunkm"))
        if area_km2 <= 0:
            continue

        data_alerta = _parse_data_iso(props.get("view_date"))
        if data_alerta > data_mais_recente:
            data_mais_recente = data_alerta

        por_uf[uf] += area_km2

        if uf == "PA" and len(detalhes_pa) < 8:
            gid = str(props.get("gid") or len(detalhes_pa))
            mun = str(props.get("municipality") or "Município no Pará").strip().title()
            classe = str(props.get("classname") or "ALERTA").strip()
            satelite = str(props.get("satellite") or "CBERS/AMAZONIA").strip()
            gid_slug = re.sub(r"[^a-zA-Z0-9_-]+", "_", gid)
            detalhes_pa.append(
                {
                    "tipo_metrica": "alerta_desmatamento",
                    "fonte": "INPE — TerraBrasilis (DETER Amazônia)",
                    "instituicao": "INPE / MCTI",
                    "identificador_original": f"deter_amz_pa_alerta:{gid_slug}",
                    "estado": "PA",
                    "municipio": mun,
                    "bioma": "Amazônia",
                    "amazonia_legal": True,
                    "latitude": None,
                    "longitude": None,
                    "data_referencia": data_alerta,
                    "periodo_rotulo": f"Alerta DETER ({classe})",
                    "valor": round(area_km2, 3),
                    "unidade": "km²",
                    "satelite_ou_metodo": f"DETER / {satelite}",
                    "nivel_confianca": "alerta_operacional",
                    "url_fonte": TERRABRASILIS_PORTAL_URL,
                    "observacao": (
                        f"Alerta operacional DETER ({classe}) em {mun}/PA "
                        f"com área de {area_km2:.3f} km²."
                    ),
                }
            )

    registros: list[dict] = []
    for uf, soma_km2 in sorted(por_uf.items()):
        registros.append(
            {
                "tipo_metrica": "alerta_desmatamento",
                "fonte": "INPE — TerraBrasilis (DETER Amazônia)",
                "instituicao": "INPE / MCTI",
                "identificador_original": f"deter_amz_uf_amostra:{uf}",
                "estado": uf,
                "municipio": None,
                "bioma": "Amazônia",
                "amazonia_legal": uf in ESTADOS_AMAZONIA_LEGAL,
                "latitude": None,
                "longitude": None,
                "data_referencia": data_mais_recente,
                "periodo_rotulo": "Amostra recente DETER WFS",
                "valor": round(soma_km2, 2),
                "unidade": "km²",
                "satelite_ou_metodo": "WFS GeoServer DETER (INPE)",
                "nivel_confianca": "alerta_operacional",
                "url_fonte": TERRABRASILIS_PORTAL_URL,
                "observacao": (
                    f"Soma de alertas DETER consultados via WFS para a UF {uf} "
                    f"({soma_km2:.2f} km²). Alertas destinam-se à fiscalização "
                    "e não equivalem à taxa consolidada anual do PRODES."
                ),
            }
        )

    registros.extend(detalhes_pa)
    return registros


def gerar_registros_serie_prodes() -> list[dict]:
    """Retorna a série histórica oficial consolidada do PRODES (Amazônia Legal e Pará)."""
    registros: list[dict] = []
    for item in SERIE_HISTORICA_OFICIAL_PRODES:
        ano = item["ano"]
        amz_km2 = item["amazonia_legal_km2"]
        pa_km2 = item["para_km2"]
        data_ref = date(ano, 7, 31)

        registros.append(
            {
                "tipo_metrica": "desmatamento_consolidado",
                "fonte": "INPE — TerraBrasilis (PRODES Amazônia Legal)",
                "instituicao": "INPE / MCTI",
                "identificador_original": f"prodes_oficial_para:{ano}",
                "estado": "PA",
                "municipio": None,
                "bioma": "Amazônia",
                "amazonia_legal": True,
                "latitude": None,
                "longitude": None,
                "data_referencia": data_ref,
                "periodo_rotulo": f"Taxa consolidada PRODES {ano}",
                "valor": float(pa_km2),
                "unidade": "km²",
                "satelite_ou_metodo": "PRODES (Landsat / Sentinel / CBERS)",
                "nivel_confianca": "consolidado_anual",
                "url_fonte": TERRABRASILIS_PORTAL_URL,
                "observacao": (
                    f"Área de desmatamento por corte raso consolidada pelo "
                    f"PRODES/INPE no Estado do Pará no ano-referência {ano}: "
                    f"{pa_km2:.0f} km² (de {amz_km2:.0f} km² na Amazônia Legal)."
                ),
            }
        )
        registros.append(
            {
                "tipo_metrica": "desmatamento_consolidado",
                "fonte": "INPE — TerraBrasilis (PRODES Amazônia Legal)",
                "instituicao": "INPE / MCTI",
                "identificador_original": f"prodes_oficial_amz_restante:{ano}",
                "estado": "AM",
                "municipio": None,
                "bioma": "Amazônia",
                "amazonia_legal": True,
                "latitude": None,
                "longitude": None,
                "data_referencia": data_ref,
                "periodo_rotulo": f"Taxa consolidada PRODES {ano} (Demais UFs Amazônia Legal)",
                "valor": float(round(amz_km2 - pa_km2, 1)),
                "unidade": "km²",
                "satelite_ou_metodo": "PRODES (Landsat / Sentinel / CBERS)",
                "nivel_confianca": "consolidado_anual",
                "url_fonte": TERRABRASILIS_PORTAL_URL,
                "observacao": (
                    f"Soma das demais UFs da Amazônia Legal no PRODES {ano}: "
                    f"{amz_km2 - pa_km2:.0f} km² (Total Amazônia Legal: {amz_km2:.0f} km²)."
                ),
            }
        )
    return registros


def coletar_deter_terrabrasilis(limite_feicoes: int = 120) -> list[dict]:
    """Consulta alertas DETER no GeoServer WFS do TerraBrasilis sem geometria pesada."""
    resposta = requisitar_http(
        DETER_WFS_URL,
        params={
            "service": "WFS",
            "version": "2.0.0",
            "request": "GetFeature",
            "typeNames": "deter-amz:deter_amz",
            "CQL_FILTER": "view_date>=2024-01-01",
            "count": min(max(limite_feicoes, 10), 300),
            "outputFormat": "application/json",
            "propertyName": (
                "gid,classname,view_date,areamunkm,municipality,uf,satellite"
            ),
        },
        timeout=20,
    )
    payload = resposta.json()
    return parsear_geojson_deter(payload)


def verificar_wfs_prodes_E_gerar_serie() -> list[dict]:
    """Valida a disponibilidade do WFS do PRODES no TerraBrasilis e retorna a série consolidada."""
    requisitar_http(
        PRODES_WFS_URL,
        params={
            "service": "WFS",
            "version": "2.0.0",
            "request": "GetFeature",
            "typeNames": "prodes-legal-amz:yearly_deforestation",
            "CQL_FILTER": "year>=2023",
            "count": 5,
            "outputFormat": "application/json",
            "propertyName": "fid,state,year,area_km,main_class",
        },
        timeout=20,
    )
    return gerar_registros_serie_prodes()
