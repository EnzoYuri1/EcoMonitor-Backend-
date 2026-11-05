# EcoMonitor Backend

API REST para monitoramento ambiental de queimadas e desmatamento. O backend
oferece autenticação JWT, cadastro e gerenciamento de ocorrências, filtros,
estatísticas para dashboard e documentação OpenAPI, servindo o frontend
Streamlit do EcoMonitor.

## Stack

- Python 3.12
- FastAPI + Uvicorn
- SQLite + SQLModel
- PyJWT
- Passlib + Bcrypt
- Requests
- Python-dotenv
- pytest + httpx2 (testes)

## Estrutura

```text
EcoMonitor-Backend/
├── app/
│   ├── main.py
│   ├── docs.py
│   ├── api/v1/
│   │   ├── api.py
│   │   ├── responses.py
│   │   └── endpoints/
│   │       ├── auth.py
│   │       ├── ocorrencias.py
│   │       └── stats.py
│   ├── core/
│   │   ├── config.py
│   │   └── security.py
│   ├── db/
│   │   └── session.py
│   ├── models/
│   │   ├── user.py
│   │   └── ocorrencia.py
│   ├── schemas/
│   │   ├── common.py
│   │   ├── info.py
│   │   ├── user.py
│   │   ├── ocorrencia.py
│   │   └── stats.py
│   └── services/
│       ├── auth_service.py
│       ├── ocorrencia_service.py
│       └── stats_service.py
├── docs/
│   └── INTEGRACAO_FRONTEND.md
├── scripts/
│   └── seed_exemplos.py
├── tests/
├── data/
├── .env.example
├── .gitignore
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

### Variáveis de ambiente

| Variável | Padrão | Descrição |
|---|---|---|
| `SECRET_KEY` | — | Chave de assinatura JWT (obrigatória) |
| `ALGORITHM` | `HS256` | Algoritmo do JWT |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | `60` | Validade do token em minutos |
| `DATABASE_URL` | `sqlite:///./data/ecomonitor.db` | Banco SQLite |
| `CORS_ORIGINS` | `http://localhost:8501,http://127.0.0.1:8501` | Origens permitidas, separadas por vírgula |

O arquivo `.env` não é versionado. O `.env.example` contém apenas valores
demonstrativos.

## Executar a API

```powershell
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload
```

- API: `http://127.0.0.1:8000`
- RapiDoc: `http://127.0.0.1:8000/docs`
- Swagger UI: `http://127.0.0.1:8000/swagger`
- ReDoc: `http://127.0.0.1:8000/redoc`
- OpenAPI JSON: `http://127.0.0.1:8000/openapi.json`
- Saúde: `http://127.0.0.1:8000/health`

O banco e as tabelas são criados automaticamente em `data/ecomonitor.db`.

### Documentação interativa

A documentação principal fica em `/docs` e usa **RapiDoc**, escolhido por ter
uma leitura mais limpa e direta que o Swagger:

- navegação lateral por grupo de endpoints;
- busca por rota;
- console para testar requisições;
- autenticação persistente entre recarregamentos;
- exemplos de payload e de resposta.

O **Swagger UI** continua disponível em `/swagger`, e o **ReDoc** em `/redoc`.

Para testar rotas protegidas:

1. Cadastre um usuário em `POST /api/v1/auth/register`.
2. Faça login em `POST /api/v1/auth/login` e copie o `access_token`.
3. Na documentação, abra a seção de autenticação e informe apenas o token.
4. As rotas protegidas usam o cabeçalho `Authorization: Bearer <token>`.

A resposta do login inclui `expires_in`, com a validade do token em segundos.
Ao receber `401`, faça login novamente.

## Endpoints

Prefixo: `/api/v1`.

### Autenticação

| Método | Rota | Autenticação | Descrição |
|---|---|---|---|
| POST | `/auth/register` | Não | Cadastrar usuário |
| POST | `/auth/login` | Não | Autenticar e retornar JWT |
| GET | `/auth/me` | Bearer | Usuário autenticado |

Login e cadastro recebem JSON. A resposta do login contém `access_token`,
`token_type` e `expires_in` (validade em segundos). Nas rotas protegidas, envie:

```http
Authorization: Bearer <access_token>
```

### Ocorrências

| Método | Rota | Autenticação | Descrição |
|---|---|---|---|
| GET | `/ocorrencias` | Bearer | Listar com filtros e paginação |
| POST | `/ocorrencias` | Bearer | Cadastrar ocorrência |
| GET | `/ocorrencias/{id}` | Bearer | Consultar por ID |
| PATCH | `/ocorrencias/{id}` | Bearer | Atualizar parcialmente (responsável) |
| DELETE | `/ocorrencias/{id}` | Bearer | Excluir (responsável) |

Filtros da listagem:

- `tipo`: `queimada` ou `desmatamento`.
- `municipio`: busca parcial, sem diferenciar maiúsculas.
- `data_inicio` e `data_fim`: datas ISO inclusivas.
- `page`: página, começando em `1` (padrão `1`).
- `page_size`: itens por página, de `1` a `100` (padrão `20`).

A listagem retorna um envelope paginado:

```json
{
  "items": [],
  "total": 0,
  "page": 1,
  "page_size": 20,
  "pages": 0
}
```

Qualquer usuário autenticado pode consultar os registros. Apenas o responsável
(`created_by`) pode alterar ou excluir. O responsável é sempre definido pelo
token, nunca pelo corpo da requisição. O `PATCH` atualiza apenas os campos
enviados; `PUT` não é aceito.

### Estatísticas

| Método | Rota | Autenticação | Descrição |
|---|---|---|---|
| GET | `/stats` | Bearer | Indicadores do dashboard |

Retorna total de ocorrências, queimadas, desmatamentos e distribuição por
município e por tipo, calculados no SQLite.

## Documentação para o frontend

O guia completo para integração com o Streamlit está em
[`docs/INTEGRACAO_FRONTEND.md`](docs/INTEGRACAO_FRONTEND.md), com exemplos de
requisições, respostas, erros, filtros e código com `requests`.

## Testes

```powershell
.\.venv\Scripts\python.exe -m pytest -v
```

Os testes usam um banco SQLite em memória e não alteram o banco local. Cobrem
autenticação, cadastro e duplicidade de email, login, tokens inválidos e
expirados, CRUD de ocorrências, paginação, filtros, permissões, validações,
estatísticas e a documentação OpenAPI.

## Dados de demonstração (opcional)

O script `scripts/seed_exemplos.py` cadastra 40 ocorrências fictícias
(20 queimadas e 20 desmatamentos) no banco configurado, distribuídas nos
últimos 12 meses e vinculadas ao usuário de id 2 (Maria). Os registros ficam
marcados com o prefixo `[exemplo]` na descrição para não se confundirem com
dados reais.

```powershell
# Cadastra os 40 exemplos (não duplica se já existirem)
.\.venv\Scripts\python.exe scripts\seed_exemplos.py

# Remove somente os registros marcados com [exemplo]
.\.venv\Scripts\python.exe scripts\seed_exemplos.py --limpar

# Remove os exemplos e cadastra novamente
.\.venv\Scripts\python.exe scripts\seed_exemplos.py --recriar
```

Use `--usuario-id N` para vincular os exemplos a outro usuário. As ocorrências
reais existentes não são alteradas nem removidas.

## Segurança

- Senhas protegidas com Bcrypt; nunca armazenadas em texto puro.
- JWT assinado com `SECRET_KEY` carregada do ambiente.
- Rotas de ocorrências e estatísticas protegidas por Bearer token.
- Edição e exclusão restritas ao responsável.
- Validação de email, senha, UF, datas e coordenadas.
- CORS restrito às origens configuradas, sem curinga com credenciais.
- `.env`, `.venv` e bancos locais ignorados pelo Git.

## Cloudflare Tunnel

Para disponibilização externa durante a apresentação:

```powershell
winget install --id Cloudflare.cloudflared --exact
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
cloudflared tunnel --url http://127.0.0.1:8000
```

A URL pública gerada deve ser usada como base da API no frontend. Túneis
rápidos são temporários; encerre o processo após a apresentação. Se o comando
`cloudflared` não for reconhecido, reabra o terminal ou use o caminho completo
`C:\Program Files (x86)\cloudflared\cloudflared.exe`. Detalhes em
[`docs/INTEGRACAO_FRONTEND.md`](docs/INTEGRACAO_FRONTEND.md#8-cloudflare-tunnel).

## Git e publicação

O repositório local usa a branch `main` e commits organizados por etapa. A
publicação no GitHub depende de autenticação prévia:

```powershell
gh auth login
gh repo create EcoMonitor-Backend --private --source . --remote origin --push
```

Nenhum repositório remoto é criado automaticamente sem autenticação e
autorização.

## Status

Implementado e testado:

- Estrutura, configuração, SQLite e CORS.
- Documentação em RapiDoc (`/docs`), Swagger UI (`/swagger`) e ReDoc (`/redoc`).
- Modelos `User` e `Ocorrencia` com relacionamento e integridade referencial.
- Cadastro, login JSON, Bcrypt e JWT com `expires_in`.
- CRUD de ocorrências com paginação, filtros e permissões.
- Atualização parcial com `PATCH` e cabeçalho `Location` na criação.
- Estatísticas agregadas no SQLite.
- Guia de integração para o frontend.

Pendente apenas de ação externa: autenticação no GitHub e publicação do
repositório privado.
