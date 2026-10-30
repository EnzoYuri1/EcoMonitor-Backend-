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

## Status

Etapa 1 concluída: estrutura, configuração, conexão com SQLite, CORS e
documentação automática. Os endpoints de negócio serão adicionados nas
próximas etapas.
