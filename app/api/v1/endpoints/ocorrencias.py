from datetime import date
from typing import Annotated

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Path,
    Query,
    Response,
    status,
)
from sqlmodel import Session

from app.api.v1.responses import (
    BAD_REQUEST_RESPONSE,
    FORBIDDEN_RESPONSE,
    NOT_FOUND_RESPONSE,
    UNAUTHORIZED_RESPONSE,
    VALIDATION_ERROR_RESPONSE,
)
from app.core.config import settings
from app.core.security import get_current_user
from app.db.session import get_session
from app.models import Ocorrencia, TipoOcorrencia, User
from app.schemas.common import Page
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
    response_model=Page[OcorrenciaRead],
    operation_id="ocorrencias_listar",
    summary="Listar ocorrências",
    description=(
        "Lista ocorrências ambientais de forma paginada. Todos os filtros "
        "são opcionais e podem ser combinados. O período é inclusivo.\n\n"
        "**Exemplo:** `GET /api/v1/ocorrencias?tipo=queimada&municipio=sin"
        "&page=1&page_size=20`"
    ),
    response_description="Página de ocorrências encontradas.",
    responses={
        400: BAD_REQUEST_RESPONSE,
        401: UNAUTHORIZED_RESPONSE,
        422: VALIDATION_ERROR_RESPONSE,
    },
)
def list_ocorrencias(
    tipo: TipoOcorrencia | None = Query(
        default=None,
        description="Filtrar por queimada ou desmatamento.",
        examples=["queimada"],
    ),
    municipio: str | None = Query(
        default=None,
        min_length=1,
        max_length=120,
        description="Busca parcial por município, sem diferenciar maiúsculas.",
        examples=["Sinop"],
    ),
    data_inicio: date | None = Query(
        default=None,
        description="Data inicial do período (AAAA-MM-DD), inclusive.",
        examples=["2026-10-01"],
    ),
    data_fim: date | None = Query(
        default=None,
        description="Data final do período (AAAA-MM-DD), inclusive.",
        examples=["2026-10-31"],
    ),
    page: int = Query(
        default=1,
        ge=1,
        description="Número da página, começando em 1.",
        examples=[1],
    ),
    page_size: int = Query(
        default=20,
        ge=1,
        le=100,
        description="Quantidade de itens por página (1 a 100).",
        examples=[20],
    ),
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> Page[OcorrenciaRead]:
    if data_inicio and data_fim and data_inicio > data_fim:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A data inicial não pode ser posterior à data final.",
        )

    ocorrencias, total = ocorrencia_service.list_ocorrencias(
        session,
        tipo=tipo,
        municipio=municipio,
        data_inicio=data_inicio,
        data_fim=data_fim,
        page=page,
        page_size=page_size,
    )
    return Page[OcorrenciaRead](
        items=ocorrencias,
        total=total,
        page=page,
        page_size=page_size,
        pages=(total + page_size - 1) // page_size,
    )


@router.post(
    "",
    response_model=OcorrenciaRead,
    status_code=status.HTTP_201_CREATED,
    operation_id="ocorrencias_criar",
    summary="Cadastrar ocorrência",
    description=(
        "Registra uma nova ocorrência vinculada automaticamente ao usuário "
        "autenticado.\n\n"
        "O campo `created_by` é definido pelo token e não deve ser enviado "
        "no corpo da requisição."
    ),
    response_description="Ocorrência cadastrada com sucesso.",
    responses={
        401: UNAUTHORIZED_RESPONSE,
        422: VALIDATION_ERROR_RESPONSE,
    },
)
def create_ocorrencia(
    ocorrencia_in: OcorrenciaCreate,
    response: Response,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> Ocorrencia:
    ocorrencia = ocorrencia_service.create_ocorrencia(
        session,
        ocorrencia_in,
        current_user.id,
    )
    response.headers["Location"] = (
        f"{settings.API_V1_STR}/ocorrencias/{ocorrencia.id}"
    )
    return ocorrencia


@router.get(
    "/{ocorrencia_id}",
    response_model=OcorrenciaRead,
    operation_id="ocorrencias_consultar",
    summary="Consultar ocorrência",
    description="Retorna uma ocorrência específica pelo identificador.",
    response_description="Ocorrência encontrada.",
    responses={
        401: UNAUTHORIZED_RESPONSE,
        404: NOT_FOUND_RESPONSE,
        422: VALIDATION_ERROR_RESPONSE,
    },
)
def get_ocorrencia(
    ocorrencia_id: Annotated[int, Path(description="ID da ocorrência.")],
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> Ocorrencia:
    return _get_or_404(session, ocorrencia_id)


@router.patch(
    "/{ocorrencia_id}",
    response_model=OcorrenciaRead,
    operation_id="ocorrencias_atualizar",
    summary="Atualizar ocorrência",
    description=(
        "Atualiza parcialmente uma ocorrência. Envie apenas os campos que "
        "deseja alterar; os demais permanecem inalterados.\n\n"
        "Somente o usuário responsável pode executar esta operação. Campos "
        "obrigatórios não podem ser anulados."
    ),
    response_description="Ocorrência atualizada com sucesso.",
    responses={
        401: UNAUTHORIZED_RESPONSE,
        403: FORBIDDEN_RESPONSE,
        404: NOT_FOUND_RESPONSE,
        422: VALIDATION_ERROR_RESPONSE,
    },
)
def update_ocorrencia(
    ocorrencia_id: Annotated[int, Path(description="ID da ocorrência.")],
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
    operation_id="ocorrencias_excluir",
    summary="Excluir ocorrência",
    description="Remove uma ocorrência. Somente o responsável pode excluir.",
    response_description="Ocorrência excluída com sucesso.",
    responses={
        401: UNAUTHORIZED_RESPONSE,
        403: FORBIDDEN_RESPONSE,
        404: NOT_FOUND_RESPONSE,
        422: VALIDATION_ERROR_RESPONSE,
    },
)
def delete_ocorrencia(
    ocorrencia_id: Annotated[int, Path(description="ID da ocorrência.")],
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> None:
    ocorrencia = _get_or_404(session, ocorrencia_id)
    _check_owner(ocorrencia, current_user.id)
    ocorrencia_service.delete_ocorrencia(session, ocorrencia)
