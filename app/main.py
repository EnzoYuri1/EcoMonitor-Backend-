from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.api import api_router
from app.core.config import settings
from app.db.session import create_db_and_tables


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Garante a criação do banco e das tabelas na inicialização."""
    create_db_and_tables()
    yield


app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    description=(
        "API REST do EcoMonitor para monitoramento de queimadas e "
        "desmatamento. Documentação interativa em `/docs` e `/redoc`."
    ),
    lifespan=lifespan,
)

if settings.CORS_ORIGINS:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type"],
    )

app.include_router(api_router, prefix=settings.API_V1_STR)


@app.get(
    "/health",
    tags=["Saúde"],
    summary="Verificar disponibilidade da API",
    description="Retorna o estado da API. Não exige autenticação.",
)
def health_check() -> dict[str, str]:
    return {"status": "ok"}
