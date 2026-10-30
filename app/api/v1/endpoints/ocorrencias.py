from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlmodel import Session

from app.core.security import get_current_user
from app.db.session import get_session
from app.models import Ocorrencia, TipoOcorrencia, User
from app.schemas.ocorrencia import (
    OcorrenciaCreate,
    OcorrenciaRead,
    OcorrenciaUpdate,
)
from app.services import ocorrencia_service

router = APIRouter(prefix="/ocorrencias", tags=["Ocorrências"])


def _get_or_404(session: Session, ocorrencia_id: int) -> Ocorrencia:
    ocorrencia = ocorrencia_service.get_ocorrencia(session, ocorrencia_id)
    if ocorrencia is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Ocorrência não encontrada.",
        )
    return ocorrencia


def _check_owner(ocorrencia: Ocorrencia, user_id: int) -> None:
    if not ocorrencia_service.usuario_e_responsavel(ocorrencia, user_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                "Apenas o responsável pode alterar ou excluir esta "
                "ocorrência."
            ),
        )


@router.get(
    "",
    response_model=list[OcorrenciaRead],
    summary="Listar ocorrências",
    description=(
        "Lista ocorrências ambientais. Todos os filtros são opcionais e "
        "podem ser combinados. O período é inclusivo."
    ),
    responses={401: {"description": "Token ausente, inválido ou expirado."}},
)
def list_ocorrencias(
    tipo: TipoOcorrencia | None = Query(
        default=None,
        description="Filtrar por queimada ou desmatamento.",
    ),
    municipio: str | None = Query(
        default=None,
        min_length=1,
        max_length=120,
        description="Busca parcial por município, sem diferenciar maiúsculas.",
    ),
    data_inicio: date | None = Query(
        default=None,
        description="Data inicial do período (AAAA-MM-DD), inclusive.",
    ),
    data_fim: date | None = Query(
        default=None,
        description="Data final do período (AAAA-MM-DD), inclusive.",
    ),
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> list[Ocorrencia]:
    if data_inicio and data_fim and data_inicio > data_fim:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A data inicial não pode ser posterior à data final.",
        )

    return ocorrencia_service.list_ocorrencias(
        session,
        tipo=tipo,
        municipio=municipio,
        data_inicio=data_inicio,
        data_fim=data_fim,
    )


@router.post(
    "",
    response_model=OcorrenciaRead,
    status_code=status.HTTP_201_CREATED,
    summary="Cadastrar ocorrência",
    description=(
        "Registra uma nova ocorrência vinculada automaticamente ao usuário "
        "autenticado."
    ),
    responses={401: {"description": "Token ausente, inválido ou expirado."}},
)
def create_ocorrencia(
    ocorrencia_in: OcorrenciaCreate,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> Ocorrencia:
    return ocorrencia_service.create_ocorrencia(
        session,
        ocorrencia_in,
        current_user.id,
    )


@router.get(
    "/{ocorrencia_id}",
    response_model=OcorrenciaRead,
    summary="Consultar ocorrência",
    description="Retorna uma ocorrência específica pelo identificador.",
    responses={
        401: {"description": "Token ausente, inválido ou expirado."},
        404: {"description": "Ocorrência não encontrada."},
    },
)
def get_ocorrencia(
    ocorrencia_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> Ocorrencia:
    return _get_or_404(session, ocorrencia_id)


@router.put(
    "/{ocorrencia_id}",
    response_model=OcorrenciaRead,
    summary="Atualizar ocorrência",
    description=(
        "Atualiza uma ocorrência. Somente o usuário responsável pode "
        "executar esta operação; campos não enviados permanecem inalterados."
    ),
    responses={
        401: {"description": "Token ausente, inválido ou expirado."},
        403: {"description": "Usuário não é o responsável pela ocorrência."},
        404: {"description": "Ocorrência não encontrada."},
    },
)
def update_ocorrencia(
    ocorrencia_id: int,
    ocorrencia_in: OcorrenciaUpdate,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> Ocorrencia:
    ocorrencia = _get_or_404(session, ocorrencia_id)
    _check_owner(ocorrencia, current_user.id)
    return ocorrencia_service.update_ocorrencia(
        session,
        ocorrencia,
        ocorrencia_in,
    )


@router.delete(
    "/{ocorrencia_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Excluir ocorrência",
    description="Remove uma ocorrência. Somente o responsável pode excluir.",
    responses={
        401: {"description": "Token ausente, inválido ou expirado."},
        403: {"description": "Usuário não é o responsável pela ocorrência."},
        404: {"description": "Ocorrência não encontrada."},
    },
)
def delete_ocorrencia(
    ocorrencia_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> None:
    ocorrencia = _get_or_404(session, ocorrencia_id)
    _check_owner(ocorrencia, current_user.id)
    ocorrencia_service.delete_ocorrencia(session, ocorrencia)
