import pytest
from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine

from app import models  # noqa: F401  # registra os modelos no metadata
from app.core.config import settings
from app.models import central as _central  # noqa: F401
from app.db.session import get_session
from app.main import app


@pytest.fixture(autouse=True)
def _default_openrouter_test_key(monkeypatch):
    if not settings.OPENROUTER_API_KEY:
        monkeypatch.setattr(settings, "OPENROUTER_API_KEY", "sk-or-test-key")


@pytest.fixture
def engine():
    """Engine SQLite em memória, isolada por teste."""
    test_engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(test_engine)
    yield test_engine
    test_engine.dispose()


@pytest.fixture
def session(engine):
    with Session(engine) as test_session:
        yield test_session


@pytest.fixture
def client(session):
    """Cliente HTTP usando o banco de teste no lugar do banco local."""

    def override_get_session():
        yield session

    app.dependency_overrides[get_session] = override_get_session
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear()
