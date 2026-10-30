from sqlalchemy import func
from sqlmodel import Session, select

from app.models import Ocorrencia, TipoOcorrencia
from app.schemas.stats import MunicipioStats, StatsRead, TipoStats


def get_stats(session: Session) -> StatsRead:
    """Calcula os indicadores ambientais a partir do banco."""
    total = session.exec(
        select(func.count()).select_from(Ocorrencia)
    ).one()

    tipos_rows = session.execute(
        select(Ocorrencia.tipo, func.count(Ocorrencia.id)).group_by(
            Ocorrencia.tipo
        )
    ).all()
    totais_por_tipo = {tipo: quantidade for tipo, quantidade in tipos_rows}

    municipios_rows = session.execute(
        select(Ocorrencia.municipio, func.count(Ocorrencia.id))
        .group_by(Ocorrencia.municipio)
        .order_by(
            func.count(Ocorrencia.id).desc(),
            Ocorrencia.municipio.asc(),
        )
    ).all()

    total_queimadas = totais_por_tipo.get(TipoOcorrencia.QUEIMADA, 0)
    total_desmatamentos = totais_por_tipo.get(
        TipoOcorrencia.DESMATAMENTO, 0
    )

    return StatsRead(
        total_ocorrencias=total,
        total_queimadas=total_queimadas,
        total_desmatamentos=total_desmatamentos,
        por_municipio=[
            MunicipioStats(municipio=municipio, total=quantidade)
            for municipio, quantidade in municipios_rows
        ],
        por_tipo=[
            TipoStats(
                tipo=tipo,
                total=totais_por_tipo.get(tipo, 0),
            )
            for tipo in TipoOcorrencia
        ],
    )
