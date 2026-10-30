from collections.abc import Generator
from pathlib import Path

from sqlalchemy import event
from sqlmodel import Session, SQLModel, create_engine

from app.core.config import BASE_DIR, settings

DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)

_SQLITE_PREFIX = "sqlite:///"


def _resolve_database_url(url: str) -> str:
    """Converte caminhos SQLite relativos em absolutos a partir da raiz."""
    if url.startswith(f"{_SQLITE_PREFIX}./"):
        relative_path = url[len(_SQLITE_PREFIX) + 2 :]
        return f"{_SQLITE_PREFIX}{(BASE_DIR / relative_path).as_posix()}"
    return url


DATABASE_URL = _resolve_database_url(settings.DATABASE_URL)

connect_args = (
    {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}
)
engine = create_engine(DATABASE_URL, connect_args=connect_args)


@event.listens_for(engine, "connect")
def _enable_sqlite_foreign_keys(dbapi_connection, connection_record) -> None:
    """Garante a integridade referencial no SQLite."""
    if DATABASE_URL.startswith("sqlite"):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()


def create_db_and_tables() -> None:
    """Cria o arquivo do banco e as tabelas registradas no SQLModel."""
    from app import models  # noqa: F401  # registra os modelos

    SQLModel.metadata.create_all(engine)


def get_session() -> Generator[Session, None, None]:
    """Fornece uma sessão de banco de dados por requisição."""
    with Session(engine) as session:
        yield session
