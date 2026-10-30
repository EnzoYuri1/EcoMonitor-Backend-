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


API_DESCRIPTION = """
API REST do EcoMonitor para monitoramento de queimadas e desmatamento.

## Como autenticar

1. Crie um usuário em `POST /api/v1/auth/register`.
2. Faça login em `POST /api/v1/auth/login` e copie o `access_token`.
3. Clique em **Authorize**, no topo da página, e informe apenas o token.
4. As rotas com cadeado exigem o cabeçalho `Authorization: Bearer <token>`.

> O cadastro não retorna token. O token tem validade configurável e, ao
> expirar, basta fazer login novamente.

## Códigos de status

| Código | Significado |
|---|---|
| `200` | Requisição concluída com sucesso. |
| `201` | Recurso criado com sucesso. |
| `204` | Recurso removido com sucesso, sem corpo na resposta. |
| `400` | Parâmetros inválidos, como período invertido. |
| `401` | Token ausente, inválido, expirado ou credenciais incorretas. |
| `403` | Usuário autenticado sem permissão sobre o recurso. |
| `404` | Recurso não encontrado. |
| `409` | Conflito, como email já cadastrado. |
| `422` | Dados enviados não passaram na validação. |

## Documentação alternativa

- **Swagger UI:** `/docs`
- **ReDoc:** `/redoc`
- **OpenAPI JSON:** `/openapi.json`
"""

TAGS_METADATA = [
    {
        "name": "Autenticação",
        "description": (
            "Cadastro, login e consulta do usuário autenticado. "
            "`register` e `login` são públicas; `me` exige Bearer token."
        ),
    },
    {
        "name": "Ocorrências",
        "description": (
            "Cadastro, consulta, filtros, atualização e exclusão de "
            "ocorrências ambientais. Todas exigem Bearer token. Somente o "
            "responsável pode alterar ou excluir."
        ),
    },
    {
        "name": "Estatísticas",
        "description": (
            "Indicadores agregados para o dashboard. Exige Bearer token."
        ),
    },
    {
        "name": "Saúde",
        "description": "Verificação de disponibilidade da API.",
    },
]

SWAGGER_UI_PARAMETERS = {
    "docExpansion": "list",
    "defaultModelsExpandDepth": -1,
    "filter": True,
    "persistAuthorization": True,
    "displayRequestDuration": True,
}


app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    description=API_DESCRIPTION,
    openapi_tags=TAGS_METADATA,
    swagger_ui_parameters=SWAGGER_UI_PARAMETERS,
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
    response_description="API disponível.",
)
def health_check() -> dict[str, str]:
    return {"status": "ok"}
