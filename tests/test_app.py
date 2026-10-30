def test_health(client):
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_documentacao_disponivel(client):
    assert client.get("/docs").status_code == 200
    assert client.get("/redoc").status_code == 200

    openapi = client.get("/openapi.json")

    assert openapi.status_code == 200
    schema = openapi.json()
    assert schema["info"]["title"] == "EcoMonitor API"
    assert "Como autenticar" in schema["info"]["description"]
    assert "/api/v1/auth/login" in schema["paths"]
    assert "/api/v1/ocorrencias" in schema["paths"]
    assert "/api/v1/stats" in schema["paths"]

    tags = {tag["name"]: tag["description"] for tag in schema["tags"]}
    assert set(tags) == {
        "Autenticação",
        "Ocorrências",
        "Estatísticas",
        "Saúde",
    }
    assert all(tags.values())


def test_swagger_ui_configurado_para_ficar_limpo(client):
    html = client.get("/docs").text

    assert '"docExpansion": "list"' in html
    assert '"defaultModelsExpandDepth": -1' in html
    assert '"filter": true' in html
    assert '"persistAuthorization": true' in html
    assert '"displayRequestDuration": true' in html


def test_openapi_usa_descricoes_de_sucesso(client):
    schema = client.get("/openapi.json").json()

    login = schema["paths"]["/api/v1/auth/login"]["post"]
    assert login["responses"]["200"]["description"] == (
        "Token JWT gerado com sucesso."
    )

    criar = schema["paths"]["/api/v1/ocorrencias"]["post"]
    assert criar["responses"]["201"]["description"] == (
        "Ocorrência cadastrada com sucesso."
    )

    stats = schema["paths"]["/api/v1/stats"]["get"]
    assert stats["responses"]["200"]["description"] == (
        "Indicadores calculados com sucesso."
    )


def test_openapi_resume_erro_de_validacao_sem_schema(client):
    schema = client.get("/openapi.json").json()

    response = schema["paths"]["/api/v1/auth/login"]["post"]["responses"][
        "422"
    ]
    content = response["content"]["application/json"]

    assert "example" in content
    assert "schema" not in content


def test_openapi_exemplos_dos_filtros(client):
    schema = client.get("/openapi.json").json()
    parametros = {
        parametro["name"]: parametro
        for parametro in schema["paths"]["/api/v1/ocorrencias"]["get"][
            "parameters"
        ]
    }

    assert parametros["tipo"]["schema"]["examples"] == ["queimada"]
    assert parametros["municipio"]["schema"]["examples"] == ["Sinop"]
    assert parametros["data_inicio"]["schema"]["examples"] == [
        "2026-10-01"
    ]
    assert parametros["data_fim"]["schema"]["examples"] == ["2026-10-31"]
