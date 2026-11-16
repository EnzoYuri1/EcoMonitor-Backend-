from datetime import datetime, timedelta, timezone
from typing import Any

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from passlib.context import CryptContext
from sqlmodel import Session

from app.core.config import settings
from app.db.session import get_session
from app.models import User

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
bearer_scheme = HTTPBearer(auto_error=False)


def get_password_hash(password: str) -> str:
    """Gera o hash Bcrypt de uma senha."""
    return pwd_context.hash(password)


def verify_password(plain_password: str, password_hash: str) -> bool:
    """Compara uma senha em texto puro com o hash armazenado."""
    return pwd_context.verify(plain_password, password_hash)


def create_access_token(
    subject: str | int,
    expires_delta: timedelta | None = None,
) -> str:
    """Cria um token JWT com identificação do usuário e expiração."""
    now = datetime.now(timezone.utc)
    expire = now + (
        expires_delta
        or timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    payload = {"sub": str(subject), "iat": now, "exp": expire}
    return jwt.encode(
        payload,
        settings.SECRET_KEY,
        algorithm=settings.ALGORITHM,
    )


def _credentials_exception() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Token inválido ou expirado.",
        headers={"WWW-Authenticate": "Bearer"},
    )


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    session: Session = Depends(get_session),
) -> User:
    """Resolve o usuário autenticado a partir do token Bearer."""
    if credentials is None:
        raise _credentials_exception()

    try:
        payload: dict[str, Any] = jwt.decode(
            credentials.credentials,
            settings.SECRET_KEY,
            algorithms=[settings.ALGORITHM],
            options={"require": ["exp", "sub"]},
        )
        user_id = int(payload["sub"])
    except (jwt.InvalidTokenError, KeyError, TypeError, ValueError) as exc:
        raise _credentials_exception() from exc

    user = session.get(User, user_id)
    if user is None:
        raise _credentials_exception()

    return user


def get_admin_user(
    current_user: User = Depends(get_current_user),
) -> User:
    """Exige o perfil administrador para operações de gestão."""
    if current_user.perfil != "administrador":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Apenas administradores podem realizar esta ação.",
        )
    return current_user
