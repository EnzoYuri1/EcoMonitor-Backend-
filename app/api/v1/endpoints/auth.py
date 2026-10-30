from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session

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
        "como hash Bcrypt."
    ),
    responses={409: {"description": "Email já cadastrado."}},
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
        "no cabeçalho Authorization."
    ),
    responses={401: {"description": "Email ou senha incorretos."}},
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
    responses={401: {"description": "Token ausente, inválido ou expirado."}},
)
def read_current_user(
    current_user: User = Depends(get_current_user),
) -> User:
    return current_user
