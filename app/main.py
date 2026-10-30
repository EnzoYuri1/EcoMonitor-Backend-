from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.api import api_router
from app.core.config import settings
from app.db.session import create_db_and_tables
from app.docs import router as docs_router
from app.schemas.info import InfoRead


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Garante a criação do banco e das tabelas na inicialização."""
    create_db_and_tables()
    yield


API_DESCRIPTION = """
API REST do EcoMonitor para monitoramento de queimadas e desmatamento.

## Documentação

- **RapiDoc (recomendado):** `/docs`
- **Swagger UI:** `/swagger`
- **ReDoc:** `/redoc`
- **OpenAPI JSON:** `/openapi.json`

## Como autenticar

1. Crie um usuário em `POST /api/v1/auth/register`.
2. Faça login em `POST /api/v1/auth/login` e copie o `access_token`.
3. Abra a seção de autenticação da documentação e informe o token.
4. As rotas protegidas usam o cabeçalho `Authorization: Bearer <token>`.

> O cadastro não retorna token. O token tem validade configurável e, ao
> expirar, basta fazer login novamente.

## Exemplo rápido em Python

```python
import requests

API = "http://127.0.0.1:8000/api/v1"

login = requests.post(
    f"{API}/auth/login",
    json={"email": "maria@example.com", "senha": "senhaSegura123"},
    timeout=10,
)
token = login.json()["access_token"]
headers = {"Authorization": f"Bearer {token}"}

pagina = requests.get(
    f"{API}/ocorrencias",
    headers=headers,
    params={"tipo": "queimada", "page": 1, "page_size": 20},
    timeout=10,
)
print(pagina.json())
```

## Paginação

As listagens retornam `items`, `total`, `page`, `page_size` e `pages`.
Use `page` e `page_size` para navegar entre os resultados.

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
"""

TAGS_METADATA = [
    {
        "name": "Informações",
        "description": "Metadados e links úteis da API.",
    },
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
            "Cadastro, consulta paginada, filtros, atualização parcial e "
            "exclusão de ocorrências ambientais. Todas exigem Bearer token. "
            "Somente o responsável pode alterar ou excluir."
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
    docs_url="/swagger",
    swagger_ui_parameters=SWAGGER_UI_PARAMETERS,
    lifespan=lifespan,
)

if settings.CORS_ORIGINS:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type"],
    )

app.include_router(docs_router)
app.include_router(api_router, prefix=settings.API_V1_STR)


@app.get(
    "/",
    response_model=InfoRead,
    operation_id="informacoes_obter",
    tags=["Informações"],
    summary="Consultar informações da API",
    description=(
        "Retorna o nome, a versão e os links da documentação e da "
        "verificação de saúde. Não exige autenticação."
    ),
    response_description="Informações da API.",
)
def root() -> InfoRead:
    return InfoRead(
        nome=settings.PROJECT_NAME,
        versao=settings.VERSION,
        docs="/docs",
        swagger="/swagger",
        redoc="/redoc",
        openapi="/openapi.json",
        health="/health",
    )


@app.get(
    "/health",
    operation_id="saude_verificar",
    tags=["Saúde"],
    summary="Verificar disponibilidade da API",
    description="Retorna o estado da API. Não exige autenticação.",
    response_description="API disponível.",
)
def health_check() -> dict[str, str]:
    return {"status": "ok"}
