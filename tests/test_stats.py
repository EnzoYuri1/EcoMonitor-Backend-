STATS_URL = "/api/v1/stats"
OCORRENCIAS_URL = "/api/v1/ocorrencias"
SENHA = "senhaSegura123"


def _autenticar(client, email: str) -> dict[str, str]:
    registro = client.post(
        "/api/v1/auth/register",
        json={"nome": "Usuário Teste", "email": email, "senha": SENHA},
    )
    assert registro.status_code == 201

    login = client.post(
        "/api/v1/auth/login",
        json={"email": email, "senha": SENHA},
    )
    assert login.status_code == 200
    return {"Authorization": f"Bearer {login.json()['access_token']}"}


def _criar(client, headers, **overrides) -> None:
    payload = {
        "tipo": "queimada",
        "municipio": "Sinop",
        "estado": "MT",
        "descricao": "Ocorrência ambiental para teste de estatísticas.",
        "data_ocorrencia": "2026-10-01",
    }
    payload.update(overrides)
    response = client.post(OCORRENCIAS_URL, json=payload, headers=headers)
    assert response.status_code == 201


def test_stats_sem_ocorrencias(client):
    headers = _autenticar(client, "autor@example.com")

    response = client.get(STATS_URL, headers=headers)

    assert response.status_code == 200
    assert response.json() == {
        "total_ocorrencias": 0,
        "total_queimadas": 0,
        "total_desmatamentos": 0,
        "por_municipio": [],
        "por_tipo": [
            {"tipo": "queimada", "total": 0},
            {"tipo": "desmatamento", "total": 0},
        ],
    }


def test_stats_globais_por_tipo_e_municipio(client):
    headers_a = _autenticar(client, "autor@example.com")
    headers_b = _autenticar(client, "leitor@example.com")

    _criar(client, headers_a, municipio="Sinop", data_ocorrencia="2026-10-01")
    _criar(client, headers_a, municipio="Sinop", data_ocorrencia="2026-10-02")
    _criar(
        client,
        headers_a,
        tipo="desmatamento",
        municipio="Sinop",
        data_ocorrencia="2026-10-03",
    )
    _criar(
        client,
        headers_a,
        municipio="Sorriso",
        data_ocorrencia="2026-10-04",
    )
    _criar(
        client,
        headers_b,
        tipo="desmatamento",
        municipio="Cuiabá",
        data_ocorrencia="2026-10-05",
    )

    response = client.get(STATS_URL, headers=headers_b)

    assert response.status_code == 200
    data = response.json()
    assert data["total_ocorrencias"] == 5
    assert data["total_queimadas"] == 3
    assert data["total_desmatamentos"] == 2

    por_municipio = {
        item["municipio"]: item["total"] for item in data["por_municipio"]
    }
    assert por_municipio == {"Sinop": 3, "Cuiabá": 1, "Sorriso": 1}
    assert data["por_municipio"][0] == {"municipio": "Sinop", "total": 3}

    assert data["por_tipo"] == [
        {"tipo": "queimada", "total": 3},
        {"tipo": "desmatamento", "total": 2},
    ]


def test_stats_exigem_autenticacao(client):
    response = client.get(STATS_URL)

    assert response.status_code == 401
