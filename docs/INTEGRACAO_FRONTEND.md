# Integração do Frontend com o EcoMonitor Backend

Este guia é destinado ao desenvolvimento do frontend Streamlit e descreve
como consumir a API REST do EcoMonitor com `requests`.

## 1. Endereço da API

Ambiente local:

```text
http://127.0.0.1:8000/api/v1
```

Documentação interativa:

- Swagger: `http://127.0.0.1:8000/docs`
- ReDoc: `http://127.0.0.1:8000/redoc`
- OpenAPI JSON: `http://127.0.0.1:8000/openapi.json`

Todas as requisições e respostas usam JSON, exceto o `DELETE`, que retorna
`204` sem corpo.

## 2. Autenticação

### 2.1 Cadastro

`POST /auth/register`

```json
{
  "nome": "Maria Silva",
  "email": "maria@example.com",
  "senha": "senhaSegura123"
}
```

Resposta `201 Created`:

```json
{
  "id": 1,
  "nome": "Maria Silva",
  "email": "maria@example.com",
  "created_at": "2026-10-30T14:00:00Z"
}
```

Regras:

- `nome`: 2 a 120 caracteres.
- `email`: único e normalizado para minúsculas.
- `senha`: mínimo de 8 caracteres e máximo de 72 bytes.
- Email já cadastrado retorna `409`.

### 2.2 Login

`POST /auth/login`

```json
{
  "email": "maria@example.com",
  "senha": "senhaSegura123"
}
```

Resposta `200 OK`:

```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer"
}
```

Credenciais inválidas retornam `401` com a mesma mensagem para email
inexistente ou senha incorreta.

### 2.3 Envio do token

Todas as rotas de ocorrências e estatísticas exigem o cabeçalho:

```http
Authorization: Bearer <access_token>
```

O token expira conforme `ACCESS_TOKEN_EXPIRE_MINUTES` (padrão: 60 minutos).
Ao receber `401`, descarte o token e solicite novo login.

No Swagger (`/docs`), clique em **Authorize** e informe apenas o token, sem
a palavra `Bearer`. O cadeado ao lado das rotas indica que elas exigem
autenticação e permanece visível mesmo depois da autorização.

### 2.4 Usuário autenticado

`GET /auth/me`

Resposta `200 OK`: mesmo formato do cadastro, sem senha ou hash.

## 3. Resumo dos endpoints

| Método | Rota | Autenticação | Descrição |
|---|---|---|---|
| POST | `/auth/register` | Não | Cadastrar usuário |
| POST | `/auth/login` | Não | Obter token JWT |
| GET | `/auth/me` | Bearer | Dados do usuário atual |
| GET | `/ocorrencias` | Bearer | Listar com filtros |
| POST | `/ocorrencias` | Bearer | Cadastrar ocorrência |
| GET | `/ocorrencias/{id}` | Bearer | Consultar por ID |
| PUT | `/ocorrencias/{id}` | Bearer | Atualizar (responsável) |
| DELETE | `/ocorrencias/{id}` | Bearer | Excluir (responsável) |
| GET | `/stats` | Bearer | Indicadores do dashboard |

## 4. Ocorrências

### 4.1 Cadastro

`POST /ocorrencias`

```json
{
  "tipo": "queimada",
  "municipio": "Sinop",
  "estado": "MT",
  "descricao": "Foco de queimada identificado próximo à rodovia.",
  "latitude": -11.8642,
  "longitude": -55.5025,
  "data_ocorrencia": "2026-10-01"
}
```

Resposta `201 Created`:

```json
{
  "id": 1,
  "tipo": "queimada",
  "municipio": "Sinop",
  "estado": "MT",
  "descricao": "Foco de queimada identificado próximo à rodovia.",
  "latitude": -11.8642,
  "longitude": -55.5025,
  "data_ocorrencia": "2026-10-01",
  "created_by": 1,
  "created_at": "2026-10-30T14:00:00Z"
}
```

O campo `created_by` é definido pelo token e não deve ser enviado pelo
frontend. Valores enviados nesse campo são ignorados.

Validações importantes:

- `tipo`: `queimada` ou `desmatamento`.
- `estado`: uma das 27 UFs; aceita minúsculas e normaliza para maiúsculas.
- `municipio`: 2 a 120 caracteres; espaços nas extremidades são removidos.
- `descricao`: 5 a 2000 caracteres.
- `latitude`: opcional, entre -90 e 90.
- `longitude`: opcional, entre -180 e 180.
- `data_ocorrencia`: obrigatória, formato `AAAA-MM-DD`, não pode ser futura.

### 4.2 Listagem e filtros

`GET /ocorrencias`

Parâmetros opcionais, combináveis:

| Parâmetro | Formato | Comportamento |
|---|---|---|
| `tipo` | `queimada` ou `desmatamento` | Igualdade |
| `municipio` | texto | Busca parcial, sem diferenciar maiúsculas |
| `data_inicio` | `AAAA-MM-DD` | Data mínima, inclusive |
| `data_fim` | `AAAA-MM-DD` | Data máxima, inclusive |

Exemplo:

```http
GET /ocorrencias?tipo=queimada&municipio=sin&data_inicio=2026-10-01&data_fim=2026-10-31
```

Resposta `200 OK`: lista de ocorrências no mesmo formato do cadastro, ordenada
da data mais recente para a mais antiga.

Se `data_inicio` for posterior a `data_fim`, a API retorna `400`.

### 4.3 Consulta por ID

`GET /ocorrencias/{id}`

- `200`: ocorrência encontrada.
- `404`: ocorrência não encontrada.

Qualquer usuário autenticado pode consultar qualquer ocorrência.

### 4.4 Atualização

`PUT /ocorrencias/{id}`

A atualização é parcial: envie apenas os campos que deseja alterar.

```json
{
  "municipio": "Cuiabá",
  "estado": "mt",
  "latitude": null
}
```

- `200`: retorna a ocorrência atualizada.
- `403`: usuário não é o responsável.
- `404`: ocorrência não encontrada.
- `422`: dados inválidos ou corpo vazio.

Campos obrigatórios (`tipo`, `municipio`, `estado`, `descricao` e
`data_ocorrencia`) não podem ser anulados. `latitude` e `longitude` podem ser
enviados como `null` para remover a coordenada.

### 4.5 Exclusão

`DELETE /ocorrencias/{id}`

- `204`: excluída com sucesso, sem corpo.
- `403`: usuário não é o responsável.
- `404`: ocorrência não encontrada.

## 5. Estatísticas

`GET /stats`

Resposta `200 OK`:

```json
{
  "total_ocorrencias": 5,
  "total_queimadas": 3,
  "total_desmatamentos": 2,
  "por_municipio": [
    {"municipio": "Sinop", "total": 3},
    {"municipio": "Cuiabá", "total": 1},
    {"municipio": "Sorriso", "total": 1}
  ],
  "por_tipo": [
    {"tipo": "queimada", "total": 3},
    {"tipo": "desmatamento", "total": 2}
  ]
}
```

Os indicadores são globais e calculados diretamente no SQLite. `por_tipo`
sempre inclui os dois tipos, mesmo quando o total é zero. `por_municipio` é
ordenado por quantidade decrescente e, em caso de empate, por município.

## 6. Erros

Formato padrão:

```json
{
  "detail": "Mensagem de erro."
}
```

Erros de validação (`422`) retornam uma lista:

```json
{
  "detail": [
    {
      "type": "date_from_datetime_parsing",
      "loc": ["body", "data_ocorrencia"],
      "msg": "Input should be a valid date or datetime, input is too short",
      "input": "01/10/2026"
    }
  ]
}
```

| Código | Situação |
|---|---|
| 400 | Período de filtro inválido |
| 401 | Token ausente, inválido, expirado ou credenciais incorretas |
| 403 | Sem permissão sobre a ocorrência |
| 404 | Recurso não encontrado |
| 409 | Email já cadastrado |
| 422 | Corpo ou parâmetros inválidos |

## 7. Exemplo de cliente Streamlit

```python
import os

import requests
import streamlit as st

API_URL = os.getenv(
    "ECOMONITOR_API_URL",
    "http://127.0.0.1:8000/api/v1",
)


def api_headers() -> dict[str, str]:
    token = st.session_state.get("token")
    return {"Authorization": f"Bearer {token}"} if token else {}


def mostrar_erro(response: requests.Response) -> None:
    try:
        detail = response.json().get("detail", "Erro inesperado.")
    except ValueError:
        detail = "Erro inesperado."
    if isinstance(detail, list):
        detail = "; ".join(
            item.get("msg", "Dados inválidos") for item in detail
        )
    st.error(detail)


def login(email: str, senha: str) -> bool:
    response = requests.post(
        f"{API_URL}/auth/login",
        json={"email": email, "senha": senha},
        timeout=10,
    )
    if response.status_code == 200:
        st.session_state["token"] = response.json()["access_token"]
        return True
    mostrar_erro(response)
    return False


def listar_ocorrencias(filtros: dict) -> list[dict]:
    response = requests.get(
        f"{API_URL}/ocorrencias",
        headers=api_headers(),
        params=filtros,
        timeout=10,
    )
    if response.status_code == 200:
        return response.json()
    mostrar_erro(response)
    return []


def criar_ocorrencia(dados: dict) -> dict | None:
    response = requests.post(
        f"{API_URL}/ocorrencias",
        headers=api_headers(),
        json=dados,
        timeout=10,
    )
    if response.status_code == 201:
        return response.json()
    mostrar_erro(response)
    return None


def obter_estatisticas() -> dict:
    response = requests.get(
        f"{API_URL}/stats",
        headers=api_headers(),
        timeout=10,
    )
    if response.status_code == 200:
        return response.json()
    mostrar_erro(response)
    return {}
```

Recomendações:

- Guarde o token apenas em `st.session_state`; nunca no código.
- Envie sempre `timeout` nas chamadas.
- Trate `401` limpando o token e voltando para a tela de login.
- Não acesse o SQLite diretamente; todo acesso passa pela API.
- Use datas ISO (`AAAA-MM-DD`) nos filtros e no formulário.

## 8. Cloudflare Tunnel

Para apresentar o backend fora da máquina local sem publicar o banco:

1. Instale o `cloudflared`:

```powershell
winget install --id Cloudflare.cloudflared --exact
```

Se o comando não for reconhecido após a instalação, reabra o terminal. Nesta
máquina, o executável também pode ser usado pelo caminho completo:

```powershell
& "C:\Program Files (x86)\cloudflared\cloudflared.exe" --version
```

2. Inicie a API:

```powershell
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

3. Em outro terminal, crie um túnel temporário:

```powershell
cloudflared tunnel --url http://127.0.0.1:8000
```

4. Copie a URL `https://<nome>.trycloudflare.com` exibida pelo Cloudflare.
   A base da API será:

```text
https://<nome>.trycloudflare.com/api/v1
```

5. No Streamlit, configure a variável `ECOMONITOR_API_URL` com essa base.

Observações:

- Túneis rápidos são temporários e a URL muda a cada execução.
- Mantenha o `.env` fora do Git e use uma `SECRET_KEY` forte.
- Exponha o túnel apenas durante a apresentação e encerre com `Ctrl+C`.
- Se um cliente browser acessar a API diretamente, inclua a origem do frontend
  em `CORS_ORIGINS`. Chamadas feitas pelo servidor Streamlit não dependem de
  CORS.
- Para URL fixa, configure um túnel nomeado no painel da Cloudflare com um
  domínio próprio.
