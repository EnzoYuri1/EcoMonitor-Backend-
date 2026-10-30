# EcoMonitor Backend

API REST para monitoramento ambiental de queimadas e desmatamento. O backend
fornece autenticação JWT e endpoints para registro, consulta e análise de
ocorrências, servindo o frontend Streamlit do projeto.

## Stack

- Python 3.12
- FastAPI + Uvicorn
- SQLite + SQLModel
- PyJWT
- Passlib + Bcrypt
- Python-dotenv

## Estrutura

```text
EcoMonitor-Backend/
├── app/
│   ├── main.py
│   ├── api/v1/
│   │   ├── api.py
│   │   └── endpoints/
│   ├── core/
│   │   ├── config.py
│   │   └── security.py
│   ├── db/
│   │   └── session.py
│   ├── models/
│   ├── schemas/
│   └── services/
├── tests/
├── data/
├── .env.example
├── requirements.txt
└── README.md
```

## Configuração local

Pré-requisitos: Python 3.12 e Git.

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
```

Gere a chave JWT e substitua o valor de `SECRET_KEY` no `.env`:

```powershell
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

## Executar a API

```powershell
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload
```

- API: http://127.0.0.1:8000
- Swagger: http://127.0.0.1:8000/docs
- ReDoc: http://127.0.0.1:8000/redoc
- Saúde: http://127.0.0.1:8000/health

## Autenticação

O cadastro e o login recebem JSON. O token retornado deve ser enviado nas
rotas protegidas como `Authorization: Bearer <token>`.

```powershell
# Cadastro
Invoke-RestMethod -Method Post http://127.0.0.1:8000/api/v1/auth/register `
  -ContentType "application/json" `
  -Body '{"nome":"Maria Silva","email":"maria@example.com","senha":"senhaSegura123"}'

# Login
$resposta = Invoke-RestMethod -Method Post http://127.0.0.1:8000/api/v1/auth/login `
  -ContentType "application/json" `
  -Body '{"email":"maria@example.com","senha":"senhaSegura123"}'

# Usuário autenticado
Invoke-RestMethod http://127.0.0.1:8000/api/v1/auth/me `
  -Headers @{ Authorization = "Bearer $($resposta.access_token)" }
```

Senhas são armazenadas somente como hash Bcrypt. Tokens expiram conforme
`ACCESS_TOKEN_EXPIRE_MINUTES` no `.env`.

## Ocorrências

Todas as rotas exigem `Authorization: Bearer <token>`.

| Método | Rota | Descrição |
|---|---|---|
| GET | `/api/v1/ocorrencias` | Lista com filtros opcionais |
| POST | `/api/v1/ocorrencias` | Cadastra ocorrência |
| GET | `/api/v1/ocorrencias/{id}` | Consulta por ID |
| PUT | `/api/v1/ocorrencias/{id}` | Atualiza (somente responsável) |
| DELETE | `/api/v1/ocorrencias/{id}` | Exclui (somente responsável) |

Filtros da listagem:

- `tipo`: `queimada` ou `desmatamento`.
- `municipio`: busca parcial, sem diferenciar maiúsculas.
- `data_inicio` e `data_fim`: datas ISO inclusivas.

Qualquer usuário autenticado pode consultar os registros. Apenas o
responsável (`created_by`) pode alterar ou excluir.

## Banco de dados

O banco SQLite é criado automaticamente em `data/ecomonitor.db` na
inicialização da API. A Etapa 2 adiciona as tabelas:

- `users`: usuários do sistema.
- `ocorrencias`: registros ambientais vinculados ao usuário responsável.

Chaves estrangeiras são habilitadas no SQLite e o email do usuário é único.

## Status

- Etapa 1: estrutura, configuração, CORS e documentação automática.
- Etapa 2: modelos `User` e `Ocorrencia`, relacionamento e criação automática
  das tabelas.
- Etapa 3: cadastro, login JSON, hash Bcrypt e proteção de rotas com JWT.
- Etapa 4: CRUD de ocorrências, filtros e permissões por responsável.

Os endpoints de negócio serão adicionados nas próximas etapas.
