from collections import defaultdict, deque
import time

from fastapi import HTTPException, Request, status

from app.core.config import settings

_WINDOWS: dict[str, deque[float]] = defaultdict(deque)
_WINDOW_SECONDS = 60.0


def limpar_rate_limit() -> None:
    """Limpa o estado em memória do rate limiter (útil para testes)."""
    _WINDOWS.clear()


def verificar_rate_limit(request: Request) -> None:
    """Aplica controle simples de requisições por IP por minuto."""
    limite = max(int(settings.CENTRAL_RATE_LIMIT_PER_MIN), 1)
    cliente_ip = (
        request.client.host if request.client and request.client.host else "local"
    )
    agora = time.monotonic()
    fila = _WINDOWS[cliente_ip]

    while fila and (agora - fila[0]) > _WINDOW_SECONDS:
        fila.popleft()

    if len(fila) >= limite:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=(
                "Limite de requisições por minuto atingido. "
                "Aguarde alguns segundos antes de tentar novamente."
            ),
        )

    fila.append(agora)
