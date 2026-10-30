from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session

from app.api.v1.responses import (
    CONFLICT_RESPONSE,
    UNAUTHORIZED_RESPONSE,
    VALIDATION_ERROR_RESPONSE,
)
from app.core.security import create_access_token, get_current_user
from app.db.session import get_session
from app.models import User
from app.schemas.user import Token, UserCreate, UserLogin, UserRead
from app.services import auth_service

router = APIRouter(prefix="/auth", tags=["Autenticação"])


@router.post(
    "/register",
    response_model=UserRead,
    status_code=status.HTTP_201_CREATED,
    summary="Cadastrar novo usuário",
    description=(
        "Cria um usuário com email único. A senha é armazenada apenas "
        "como hash Bcrypt.\n\n"
        "**Regras:** nome entre 2 e 120 caracteres; email válido e único; "
        "senha entre 8 e 72 caracteres."
    ),
    response_description="Usuário criado com sucesso.",
    responses={
        409: CONFLICT_RESPONSE,
        422: VALIDATION_ERROR_RESPONSE,
    },
)
def register(
    user_in: UserCreate,
    session: Session = Depends(get_session),
) -> User:
    if auth_service.get_user_by_email(session, user_in.email) is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email já cadastrado.",
        )

    try:
        return auth_service.create_user(session, user_in)
    except IntegrityError as exc:
        session.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email já cadastrado.",
        ) from exc


@router.post(
    "/login",
    response_model=Token,
    summary="Autenticar usuário",
    description=(
        "Valida email e senha em JSON e retorna um token JWT para uso "
        "no cabeçalho Authorization.\n\n"
        "Copie o `access_token` e clique em **Authorize** para liberar as "
        "rotas protegidas."
    ),
    response_description="Token JWT gerado com sucesso.",
    responses={
        401: {"description": "Email ou senha incorretos."},
        422: VALIDATION_ERROR_RESPONSE,
    },
)
def login(
    credentials: UserLogin,
    session: Session = Depends(get_session),
) -> Token:
    user = auth_service.authenticate_user(
        session,
        credentials.email,
        credentials.senha,
    )
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Email ou senha incorretos.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return Token(access_token=create_access_token(user.id))


@router.get(
    "/me",
    response_model=UserRead,
    summary="Consultar usuário autenticado",
    description=(
        "Retorna os dados do usuário identificado pelo token JWT enviado "
        "no cabeçalho Authorization."
    ),
    response_description="Dados do usuário autenticado.",
    responses={401: UNAUTHORIZED_RESPONSE},
)
def read_current_user(
    current_user: User = Depends(get_current_user),
) -> User:
    return current_user
