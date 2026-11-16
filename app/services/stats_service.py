from sqlalchemy import func
from sqlmodel import Session, select

from app.models import Ocorrencia, TipoOcorrencia, User
from app.schemas.stats import MunicipioStats, StatsRead, TipoStats


def get_stats(session: Session, current_user: User) -> StatsRead:
    """Calcula indicadores somente dos registros visíveis ao usuário."""
    filtros = []
    if current_user.perfil != "administrador":
        filtros.append(
            (Ocorrencia.created_by == current_user.id)
            | (Ocorrencia.responsavel_id == current_user.id)
        )

    total_query = select(func.count()).select_from(Ocorrencia)
    if filtros:
        total_query = total_query.where(*filtros)
    total = session.exec(total_query).one()

    tipos_query = select(Ocorrencia.tipo, func.count(Ocorrencia.id))
    municipios_query = select(
        Ocorrencia.municipio,
        func.count(Ocorrencia.id),
    )
    if filtros:
        tipos_query = tipos_query.where(*filtros)
        municipios_query = municipios_query.where(*filtros)
    tipos_rows = session.execute(
        tipos_query.group_by(Ocorrencia.tipo)
    ).all()
    totais_por_tipo = {tipo: quantidade for tipo, quantidade in tipos_rows}

    municipios_rows = session.execute(
        municipios_query
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
