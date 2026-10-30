from fastapi import APIRouter, Depends
from sqlmodel import Session

from app.core.security import get_current_user
from app.db.session import get_session
from app.models import User
from app.schemas.stats import StatsRead
from app.services import stats_service

router = APIRouter(prefix="/stats", tags=["Estatísticas"])


@router.get(
    "",
    response_model=StatsRead,
    summary="Obter estatísticas ambientais",
    description=(
        "Retorna totais de ocorrências, queimadas, desmatamentos e a "
        "distribuição por município e por tipo, calculados diretamente no "
        "banco SQLite."
    ),
    responses={401: {"description": "Token ausente, inválido ou expirado."}},
)
def get_stats(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> StatsRead:
    return stats_service.get_stats(session)
