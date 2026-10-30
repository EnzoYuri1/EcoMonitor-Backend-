from datetime import date, timedelta

BASE = "/api/v1/ocorrencias"
SENHA = "senhaSegura123"


def _autenticar(client, email: str) -> tuple[dict[str, str], int]:
    registro = client.post(
        "/api/v1/auth/register",
        json={"nome": "Usuário Teste", "email": email, "senha": SENHA},
    )
    assert registro.status_code == 201
    user_id = registro.json()["id"]

    login = client.post(
        "/api/v1/auth/login",
        json={"email": email, "senha": SENHA},
    )
    assert login.status_code == 200
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    return headers, user_id


def _payload(**overrides):
    payload = {
        "tipo": "queimada",
        "municipio": "Sinop",
        "estado": "MT",
        "descricao": "Foco de queimada identificado na região.",
        "latitude": -11.8642,
        "longitude": -55.5025,
        "data_ocorrencia": "2026-10-01",
    }
    payload.update(overrides)
    return payload


def _criar(client, headers, **overrides) -> dict:
    response = client.post(BASE, json=_payload(**overrides), headers=headers)
    assert response.status_code == 201
    return response.json()


def test_cadastro_de_ocorrencia(client):
    headers, user_id = _autenticar(client, "autor@example.com")

    response = client.post(BASE, json=_payload(), headers=headers)

    assert response.status_code == 201
    data = response.json()
    assert data["id"] > 0
    assert data["tipo"] == "queimada"
    assert data["municipio"] == "Sinop"
    assert data["created_by"] == user_id
    assert data["created_at"]
    assert response.headers["location"] == f"{BASE}/{data['id']}"


def test_created_by_do_corpo_e_ignorado(client):
    headers, user_id = _autenticar(client, "autor@example.com")

    response = client.post(
        BASE,
        json=_payload(created_by=9999),
        headers=headers,
    )

    assert response.status_code == 201
    assert response.json()["created_by"] == user_id


def test_rotas_de_ocorrencias_exigem_autenticacao(client):
    assert client.get(BASE).status_code == 401
    assert client.post(BASE, json=_payload()).status_code == 401
    assert client.get(f"{BASE}/1").status_code == 401
    assert (
        client.patch(f"{BASE}/1", json={"municipio": "Sinop"}).status_code
        == 401
    )
    assert client.delete(f"{BASE}/1").status_code == 401


def test_listagem_visivel_para_todos_autenticados(client):
    headers_a, _ = _autenticar(client, "autor@example.com")
    headers_b, _ = _autenticar(client, "leitor@example.com")
    _criar(client, headers_a, tipo="queimada", municipio="Sinop")
    _criar(client, headers_a, tipo="desmatamento", municipio="Sorriso")

    response = client.get(BASE, headers=headers_b)

    assert response.status_code == 200
    dados = response.json()
    assert dados["total"] == 2
    assert len(dados["items"]) == 2


def test_listagem_paginada(client):
    headers, _ = _autenticar(client, "autor@example.com")
    for dia in range(1, 6):
        _criar(
            client,
            headers,
            data_ocorrencia=f"2026-10-{dia:02d}",
            municipio=f"Cidade {dia}",
        )

    primeira = client.get(
        BASE,
        params={"page": 1, "page_size": 2},
        headers=headers,
    )
    assert primeira.status_code == 200
    dados = primeira.json()
    assert dados["total"] == 5
    assert dados["page"] == 1
    assert dados["page_size"] == 2
    assert dados["pages"] == 3
    assert [item["municipio"] for item in dados["items"]] == [
        "Cidade 5",
        "Cidade 4",
    ]

    ultima = client.get(
        BASE,
        params={"page": 3, "page_size": 2},
        headers=headers,
    )
    assert len(ultima.json()["items"]) == 1

    vazia = client.get(
        BASE,
        params={"page": 9, "page_size": 2},
        headers=headers,
    )
    assert vazia.json()["items"] == []
    assert vazia.json()["total"] == 5


def test_paginacao_com_parametros_invalidos(client):
    headers, _ = _autenticar(client, "autor@example.com")

    assert (
        client.get(BASE, params={"page": 0}, headers=headers).status_code
        == 422
    )
    assert (
        client.get(
            BASE,
            params={"page_size": 101},
            headers=headers,
        ).status_code
        == 422
    )


def test_filtro_por_tipo(client):
    headers, _ = _autenticar(client, "autor@example.com")
    _criar(client, headers, tipo="queimada")
    _criar(client, headers, tipo="desmatamento", municipio="Sorriso")

    response = client.get(BASE, params={"tipo": "queimada"}, headers=headers)

    assert response.status_code == 200
    dados = response.json()["items"]
    assert len(dados) == 1
    assert dados[0]["tipo"] == "queimada"

    invalido = client.get(BASE, params={"tipo": "invalido"}, headers=headers)
    assert invalido.status_code == 422


def test_filtro_por_municipio_parcial_e_sem_caixa(client):
    headers, _ = _autenticar(client, "autor@example.com")
    _criar(client, headers, municipio="Sinop")
    _criar(client, headers, municipio="Sorriso")

    response = client.get(BASE, params={"municipio": "SIN"}, headers=headers)

    assert response.status_code == 200
    dados = response.json()["items"]
    assert len(dados) == 1
    assert dados[0]["municipio"] == "Sinop"


def test_filtro_por_periodo_inclusivo(client):
    headers, _ = _autenticar(client, "autor@example.com")
    _criar(client, headers, data_ocorrencia="2026-10-01")
    _criar(client, headers, data_ocorrencia="2026-10-10")
    _criar(client, headers, data_ocorrencia="2026-10-20")

    response = client.get(
        BASE,
        params={"data_inicio": "2026-10-05", "data_fim": "2026-10-15"},
        headers=headers,
    )

    assert response.status_code == 200
    dados = response.json()["items"]
    assert len(dados) == 1
    assert dados[0]["data_ocorrencia"] == "2026-10-10"

    exato = client.get(
        BASE,
        params={"data_inicio": "2026-10-10", "data_fim": "2026-10-10"},
        headers=headers,
    )
    assert len(exato.json()["items"]) == 1


def test_periodo_invalido_retorna_400(client):
    headers, _ = _autenticar(client, "autor@example.com")

    response = client.get(
        BASE,
        params={"data_inicio": "2026-10-20", "data_fim": "2026-10-01"},
        headers=headers,
    )

    assert response.status_code == 400
    assert "posterior" in response.json()["detail"]


def test_consulta_por_id_e_nao_encontrado(client):
    headers, _ = _autenticar(client, "autor@example.com")
    ocorrencia = _criar(client, headers)

    response = client.get(f"{BASE}/{ocorrencia['id']}", headers=headers)
    assert response.status_code == 200
    assert response.json()["id"] == ocorrencia["id"]

    ausente = client.get(f"{BASE}/999999", headers=headers)
    assert ausente.status_code == 404


def test_atualizacao_pelo_responsavel(client):
    headers, user_id = _autenticar(client, "autor@example.com")
    ocorrencia = _criar(client, headers)

    response = client.patch(
        f"{BASE}/{ocorrencia['id']}",
        json={"municipio": "Cuiabá", "estado": "mt", "latitude": None},
        headers=headers,
    )

    assert response.status_code == 200
    data = response.json()
    assert data["municipio"] == "Cuiabá"
    assert data["estado"] == "MT"
    assert data["latitude"] is None
    assert data["tipo"] == ocorrencia["tipo"]
    assert data["created_by"] == user_id
    assert data["created_at"] == ocorrencia["created_at"]


def test_atualizacao_por_outro_usuario_retorna_403(client):
    headers_a, _ = _autenticar(client, "autor@example.com")
    headers_b, _ = _autenticar(client, "leitor@example.com")
    ocorrencia = _criar(client, headers_a)

    response = client.patch(
        f"{BASE}/{ocorrencia['id']}",
        json={"municipio": "Alterado"},
        headers=headers_b,
    )

    assert response.status_code == 403
    consulta = client.get(f"{BASE}/{ocorrencia['id']}", headers=headers_a)
    assert consulta.json()["municipio"] == "Sinop"


def test_atualizacao_de_ocorrencia_inexistente_retorna_404(client):
    headers, _ = _autenticar(client, "autor@example.com")

    response = client.patch(
        f"{BASE}/999999",
        json={"municipio": "Cuiabá"},
        headers=headers,
    )

    assert response.status_code == 404


def test_validacoes_de_atualizacao(client):
    headers, _ = _autenticar(client, "autor@example.com")
    ocorrencia = _criar(client, headers)
    url = f"{BASE}/{ocorrencia['id']}"
    amanha = (date.today() + timedelta(days=1)).isoformat()

    assert client.patch(url, json={}, headers=headers).status_code == 422
    assert (
        client.patch(
            url,
            json={"municipio": None},
            headers=headers,
        ).status_code
        == 422
    )
    assert (
        client.patch(url, json={"estado": "XX"}, headers=headers).status_code
        == 422
    )
    assert (
        client.patch(
            url,
            json={"data_ocorrencia": amanha},
            headers=headers,
        ).status_code
        == 422
    )
    assert (
        client.patch(url, json={"latitude": 100}, headers=headers).status_code
        == 422
    )


def test_exclusao_pelo_responsavel(client):
    headers, _ = _autenticar(client, "autor@example.com")
    ocorrencia = _criar(client, headers)

    response = client.delete(f"{BASE}/{ocorrencia['id']}", headers=headers)

    assert response.status_code == 204
    consulta = client.get(f"{BASE}/{ocorrencia['id']}", headers=headers)
    assert consulta.status_code == 404


def test_exclusao_por_outro_usuario_retorna_403(client):
    headers_a, _ = _autenticar(client, "autor@example.com")
    headers_b, _ = _autenticar(client, "leitor@example.com")
    ocorrencia = _criar(client, headers_a)

    response = client.delete(f"{BASE}/{ocorrencia['id']}", headers=headers_b)

    assert response.status_code == 403
    assert (
        client.get(f"{BASE}/{ocorrencia['id']}", headers=headers_a).status_code
        == 200
    )


def test_exclusao_de_ocorrencia_inexistente_retorna_404(client):
    headers, _ = _autenticar(client, "autor@example.com")

    response = client.delete(f"{BASE}/999999", headers=headers)

    assert response.status_code == 404


def test_validacoes_de_cadastro(client):
    headers, _ = _autenticar(client, "autor@example.com")
    amanha = (date.today() + timedelta(days=1)).isoformat()

    assert (
        client.post(
            BASE,
            json=_payload(tipo="invalido"),
            headers=headers,
        ).status_code
        == 422
    )
    assert (
        client.post(
            BASE,
            json=_payload(estado="XX"),
            headers=headers,
        ).status_code
        == 422
    )
    assert (
        client.post(
            BASE,
            json=_payload(data_ocorrencia=amanha),
            headers=headers,
        ).status_code
        == 422
    )
    assert (
        client.post(
            BASE,
            json=_payload(latitude=91),
            headers=headers,
        ).status_code
        == 422
    )
    assert (
        client.post(
            BASE,
            json=_payload(descricao="abc"),
            headers=headers,
        ).status_code
        == 422
    )


def test_normalizacao_de_municipio_e_estado(client):
    headers, _ = _autenticar(client, "autor@example.com")

    response = client.post(
        BASE,
        json=_payload(municipio="  Sinop  ", estado="mt"),
        headers=headers,
    )

    assert response.status_code == 201
    data = response.json()
    assert data["municipio"] == "Sinop"
    assert data["estado"] == "MT"
