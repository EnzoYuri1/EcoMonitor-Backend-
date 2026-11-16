import csv
from datetime import date, datetime
import io

from app.core.config import settings
from app.integrations.base import IntegrationError, requisitar_http

FIRMS_AREA_BASE_URL = "https://firms.modaps.eosdis.nasa.gov/api/area/csv"
# Bounding box aproximada do Estado do Pará (west,south,east,north)
BBOX_PARA = "-58.9,-9.9,-46.0,2.6"


def firms_configurada() -> bool:
    return bool((settings.FIRMS_MAP_KEY or "").strip())


def parsear_csv_firms(csv_texto: str) -> list[dict]:
    """Processa CSV retornado pela API NASA FIRMS (VIIRS/MODIS) para o Pará."""
    if not csv_texto or not csv_texto.strip():
        return []
    leitor = csv.DictReader(io.StringIO(csv_texto))
    total = 0
    frp_soma = 0.0
    data_ref = date.today()

    for linha in leitor:
        if not isinstance(linha, dict):
            continue
        total += 1
        try:
            frp_soma += float(linha.get("frp") or 0.0)
        except ValueError:
            pass
        acq_date = (linha.get("acq_date") or "").strip()
        if acq_date:
            try:
                data_ref = datetime.strptime(acq_date, "%Y-%m-%d").date()
            except ValueError:
                pass

    if total == 0:
        return []

    return [
        {
            "tipo_metrica": "foco_de_calor",
            "fonte": "NASA FIRMS (VIIRS SNPP)",
            "instituicao": "NASA / EOSDIS",
            "identificador_original": f"nasa_firms_pa:{data_ref.isoformat()}",
            "estado": "PA",
            "municipio": None,
            "bioma": "Amazônia",
            "amazonia_legal": True,
            "latitude": None,
            "longitude": None,
            "data_referencia": data_ref,
            "periodo_rotulo": f"Detecções 24h NASA FIRMS ({data_ref.strftime('%d/%m/%Y')})",
            "valor": float(total),
            "unidade": "focos",
            "satelite_ou_metodo": "VIIRS_SNPP_NRT",
            "nivel_confianca": "oficial",
            "url_fonte": "https://firms.modaps.eosdis.nasa.gov/",
            "observacao": (
                f"{total} detecções termais via satélite VIIRS SNPP sobre o "
                f"recorte do Pará (FRP acumulado: {frp_soma:.1f} MW)."
            ),
        }
    ]


def coletar_focos_firms_para() -> list[dict]:
    """Consulta a API NASA FIRMS quando FIRMS_MAP_KEY está configurada."""
    chave = (settings.FIRMS_MAP_KEY or "").strip()
    if not chave:
        raise IntegrationError(
            "FIRMS_MAP_KEY não configurada. Integração opcional inativa."
        )
    url = f"{FIRMS_AREA_BASE_URL}/{chave}/VIIRS_SNPP_NRT/{BBOX_PARA}/1"
    resposta = requisitar_http(url, timeout=20)
    return parsear_csv_firms(resposta.text)
