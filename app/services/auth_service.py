from sqlmodel import Session, select

from app.core.security import get_password_hash, verify_password
from app.models import User
from app.schemas.user import UserCreate


def get_user_by_email(session: Session, email: str) -> User | None:
    """Busca um usuário pelo email normalizado."""
    statement = select(User).where(User.email == email)
    return session.exec(statement).first()


def create_user(session: Session, user_in: UserCreate) -> User:
    """Cria um usuário com a senha protegida por hash."""
    user = User(
        nome=user_in.nome,
        email=user_in.email,
        senha_hash=get_password_hash(user_in.senha),
    )
    session.add(user)
    session.commit()
    session.refresh(user)
    return user


def authenticate_user(
    session: Session,
    email: str,
    senha: str,
) -> User | None:
    """Valida as credenciais e retorna o usuário correspondente."""
    user = get_user_by_email(session, email)
    if user is None or not verify_password(senha, user.senha_hash):
        return None
    return user
