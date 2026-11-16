from collections.abc import Generator
from pathlib import Path

from sqlalchemy import event, inspect, text
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
    """Cria as tabelas e adiciona campos de workflow a bancos existentes."""
    from app import models  # noqa: F401  # registra os modelos

    SQLModel.metadata.create_all(engine)

    colunas_adicionais = {
        "users": {
            "perfil": "VARCHAR(20) NOT NULL DEFAULT 'funcionario'",
        },
        "ocorrencias": {
            "status": "VARCHAR(24) NOT NULL DEFAULT 'registrada'",
            "prioridade": "VARCHAR(12) NOT NULL DEFAULT 'media'",
            "prazo": "DATE",
            "responsavel_id": "INTEGER REFERENCES users(id)",
            "resolucao": "VARCHAR(4000)",
            "observacao_validacao": "VARCHAR(2000)",
        },
    }

    with engine.begin() as connection:
        tabelas = set(inspect(connection).get_table_names())
        for tabela, colunas in colunas_adicionais.items():
            if tabela not in tabelas:
                continue
            existentes = {
                coluna["name"]
                for coluna in inspect(connection).get_columns(tabela)
            }
            for nome, definicao in colunas.items():
                if nome not in existentes:
                    connection.execute(
                        text(
                            f"ALTER TABLE {tabela} ADD COLUMN "
                            f"{nome} {definicao}"
                        )
                    )

        connection.execute(
            text(
                "CREATE INDEX IF NOT EXISTS ix_ocorrencias_status "
                "ON ocorrencias (status)"
            )
        )
        connection.execute(
            text(
                "CREATE INDEX IF NOT EXISTS ix_ocorrencias_responsavel_id "
                "ON ocorrencias (responsavel_id)"
            )
        )


def get_session() -> Generator[Session, None, None]:
    """Fornece uma sessão de banco de dados por requisição."""
    with Session(engine) as session:
        yield session
