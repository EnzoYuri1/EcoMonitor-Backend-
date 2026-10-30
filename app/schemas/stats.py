from pydantic import BaseModel, ConfigDict

from app.models import TipoOcorrencia


class MunicipioStats(BaseModel):
    municipio: str
    total: int


class TipoStats(BaseModel):
    tipo: TipoOcorrencia
    total: int


class StatsRead(BaseModel):
    total_ocorrencias: int
    total_queimadas: int
    total_desmatamentos: int
    por_municipio: list[MunicipioStats]
    por_tipo: list[TipoStats]

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "total_ocorrencias": 5,
                "total_queimadas": 3,
                "total_desmatamentos": 2,
                "por_municipio": [
                    {"municipio": "Sinop", "total": 3},
                    {"municipio": "Cuiabá", "total": 1},
                    {"municipio": "Sorriso", "total": 1},
                ],
                "por_tipo": [
                    {"tipo": "queimada", "total": 3},
                    {"tipo": "desmatamento", "total": 2},
                ],
            }
        }
    )
