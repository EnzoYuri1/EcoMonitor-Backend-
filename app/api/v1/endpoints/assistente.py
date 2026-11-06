from fastapi import APIRouter, Depends
from sqlmodel import Session

from app.api.v1.responses import (
    RATE_LIMIT_RESPONSE,
    UNAVAILABLE_RESPONSE,
    UNAUTHORIZED_RESPONSE,
    UPSTREAM_ERROR_RESPONSE,
    VALIDATION_ERROR_RESPONSE,
)
from app.core.security import get_current_user
from app.db.session import get_session
from app.models import User
from app.schemas.assistente import AssistenteRequest, AssistenteResponse
from app.services import assistente_service

router = APIRouter(prefix="/assistente", tags=["Assistente"])


@router.post(
    "",
    response_model=AssistenteResponse,
    operation_id="assistente_perguntar",
    summary="Perguntar ao assistente de IA",
    description=(
        "Envia uma dúvida sobre o EcoMonitor em português e recebe uma "
        "orientação baseada no guia do analista e nas estatísticas atuais "
        "do banco.\n\n"
        "O assistente somente orienta: ele não cria, edita nem exclui "
        "dados, e não substitui a avaliação técnica ou legal do analista.\n\n"
        "Limites por usuário: 1 pergunta a cada 3 segundos e 40 por dia. "
        "A cota diária gratuita do OpenRouter também se aplica."
    ),
    response_description="Resposta gerada pelo modelo gratuito configurado.",
    responses={
        401: UNAUTHORIZED_RESPONSE,
        422: VALIDATION_ERROR_RESPONSE,
        429: RATE_LIMIT_RESPONSE,
        502: UPSTREAM_ERROR_RESPONSE,
        503: UNAVAILABLE_RESPONSE,
    },
)
def perguntar(
    request: AssistenteRequest,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> AssistenteResponse:
    """Responde uma dúvida sobre o EcoMonitor usando o OpenRouter."""
    resposta, modelo = assistente_service.obter_resposta(
        session, request, current_user.id
    )
    return AssistenteResponse(resposta=resposta, modelo=modelo)
