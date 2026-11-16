from getpass import getpass
import sys

from sqlmodel import Session

from app.core.security import get_password_hash
from app.db.session import create_db_and_tables, engine
from app.models import User
from app.schemas.user import UserCreate
from app.services.auth_service import get_user_by_email


def criar_administrador() -> None:
    nome = input("Nome do administrador: ").strip()
    email = input("Email do administrador: ").strip().lower()
    senha = getpass("Senha (mínimo 8 caracteres): ")
    confirmacao = getpass("Confirme a senha: ")
    if senha != confirmacao:
        raise SystemExit("As senhas não coincidem.")

    dados = UserCreate(nome=nome, email=email, senha=senha)
    with Session(engine) as session:
        usuario = get_user_by_email(session, str(dados.email))
        if usuario is None:
            usuario = User(
                nome=dados.nome,
                email=str(dados.email),
                senha_hash=get_password_hash(dados.senha),
                perfil="administrador",
            )
            session.add(usuario)
        else:
            usuario.perfil = "administrador"
            session.add(usuario)

        session.commit()
        print(f"Perfil administrador habilitado para {usuario.email}.")


def main() -> None:
    create_db_and_tables()
    if len(sys.argv) != 2 or sys.argv[1] != "create-admin":
        raise SystemExit("Uso: python -m app.cli create-admin")
    criar_administrador()


if __name__ == "__main__":
    main()
