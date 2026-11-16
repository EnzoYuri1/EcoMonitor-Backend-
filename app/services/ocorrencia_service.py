from datetime import date

from sqlalchemy import func
from sqlmodel import Session, select

from app.models import (
    Ocorrencia,
    OcorrenciaAtividade,
    OcorrenciaEvidencia,
    OcorrenciaHistorico,
    TipoOcorrencia,
    User,
)
from app.schemas.ocorrencia import OcorrenciaCreate, OcorrenciaUpdate
from app.services.workflow_service import EVIDENCIAS_DIR


def create_ocorrencia(
    session: Session,
    ocorrencia_in: OcorrenciaCreate,
    user_id: int,
) -> Ocorrencia:
    """Cria uma ocorrência vinculada ao usuário autenticado."""
    ocorrencia = Ocorrencia(
        **ocorrencia_in.model_dump(),
        created_by=user_id,
    )
    session.add(ocorrencia)
    session.commit()
    session.refresh(ocorrencia)
    session.add(
        OcorrenciaHistorico(
            ocorrencia_id=ocorrencia.id,
            ator_id=user_id,
            acao="registrada",
            descricao="Ocorrência registrada.",
        )
    )
    session.commit()
    return ocorrencia


def list_ocorrencias(
    session: Session,
    tipo: TipoOcorrencia | None = None,
    municipio: str | None = None,
    data_inicio: date | None = None,
    data_fim: date | None = None,
    page: int = 1,
    page_size: int = 20,
    current_user: User | None = None,
) -> tuple[list[Ocorrencia], int]:
    """Lista ocorrências paginadas com filtros opcionais."""
    filtros = []

    if tipo is not None:
        filtros.append(Ocorrencia.tipo == tipo)
    if municipio:
        valor = municipio.strip().lower()
        filtros.append(
            func.lower(Ocorrencia.municipio).contains(valor, autoescape=True)
        )
    if data_inicio is not None:
        filtros.append(Ocorrencia.data_ocorrencia >= data_inicio)
    if data_fim is not None:
        filtros.append(Ocorrencia.data_ocorrencia <= data_fim)
    if current_user is not None and current_user.perfil != "administrador":
        filtros.append(
            (Ocorrencia.created_by == current_user.id)
            | (Ocorrencia.responsavel_id == current_user.id)
        )

    total_statement = select(func.count()).select_from(Ocorrencia)
    data_statement = select(Ocorrencia)
    if filtros:
        total_statement = total_statement.where(*filtros)
        data_statement = data_statement.where(*filtros)

    total = session.exec(total_statement).one()
    data_statement = (
        data_statement.order_by(
            Ocorrencia.data_ocorrencia.desc(),
            Ocorrencia.id.desc(),
        )
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    ocorrencias = list(session.exec(data_statement).all())
    return ocorrencias, total


def get_ocorrencia(
    session: Session,
    ocorrencia_id: int,
) -> Ocorrencia | None:
    """Busca uma ocorrência pelo identificador."""
    return session.get(Ocorrencia, ocorrencia_id)


def update_ocorrencia(
    session: Session,
    ocorrencia: Ocorrencia,
    ocorrencia_in: OcorrenciaUpdate,
) -> Ocorrencia:
    """Atualiza somente os campos enviados na requisição."""
    for campo, valor in ocorrencia_in.model_dump(exclude_unset=True).items():
        setattr(ocorrencia, campo, valor)

    session.add(ocorrencia)
    session.commit()
    session.refresh(ocorrencia)
    return ocorrencia


def delete_ocorrencia(session: Session, ocorrencia: Ocorrencia) -> None:
    """Remove uma ocorrência do banco."""
    evidencias = session.exec(
        select(OcorrenciaEvidencia).where(
            OcorrenciaEvidencia.ocorrencia_id == ocorrencia.id
        )
    ).all()
    atividades = session.exec(
        select(OcorrenciaAtividade).where(
            OcorrenciaAtividade.ocorrencia_id == ocorrencia.id
        )
    ).all()
    historico = session.exec(
        select(OcorrenciaHistorico).where(
            OcorrenciaHistorico.ocorrencia_id == ocorrencia.id
        )
    ).all()
    arquivos = [EVIDENCIAS_DIR / item.arquivo_salvo for item in evidencias]
    for item in evidencias + atividades + historico:
        session.delete(item)
    session.delete(ocorrencia)
    session.commit()
    for arquivo in arquivos:
        arquivo.unlink(missing_ok=True)

