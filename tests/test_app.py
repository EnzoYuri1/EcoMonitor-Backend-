def test_health(client):
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_raiz_retorna_links_da_api(client):
    response = client.get("/")

    assert response.status_code == 200
    assert response.json() == {
        "nome": "EcoMonitor API",
        "versao": "0.1.0",
        "docs": "/docs",
        "swagger": "/swagger",
        "redoc": "/redoc",
        "openapi": "/openapi.json",
        "health": "/health",
    }


def test_documentacao_disponivel(client):
    assert client.get("/docs").status_code == 200
    assert client.get("/swagger").status_code == 200
    assert client.get("/redoc").status_code == 200

    openapi = client.get("/openapi.json")

    assert openapi.status_code == 200
    schema = openapi.json()
    assert schema["info"]["title"] == "EcoMonitor API"
    assert "Como autenticar" in schema["info"]["description"]
    assert "/api/v1/auth/login" in schema["paths"]
    assert "/api/v1/ocorrencias" in schema["paths"]
    assert "/api/v1/stats" in schema["paths"]
    assert "/" in schema["paths"]
    assert "/health" in schema["paths"]

    tags = {tag["name"]: tag["description"] for tag in schema["tags"]}
    assert set(tags) == {
        "Informações",
        "Autenticação",
        "Ocorrências",
        "Estatísticas",
        "Saúde",
    }
    assert all(tags.values())


def test_docs_usa_rapidoc(client):
    response = client.get("/docs")

    assert response.status_code == 200
    assert "rapidoc" in response.text.lower()
    assert 'spec-url="/openapi.json"' in response.text
    assert 'render-style="read"' in response.text
    assert 'show-components="false"' in response.text
    assert 'persist-auth="true"' in response.text


def test_swagger_ui_configurado_para_ficar_limpo(client):
    response = client.get("/swagger")

    assert response.status_code == 200
    html = response.text
    assert '"docExpansion": "list"' in html
    assert '"defaultModelsExpandDepth": -1' in html
    assert '"filter": true' in html
    assert '"persistAuthorization": true' in html
    assert '"displayRequestDuration": true' in html


def test_openapi_tem_operation_ids_estaveis(client):
    schema = client.get("/openapi.json").json()

    operation_ids = {
        operation["operationId"]
        for methods in schema["paths"].values()
        for operation in methods.values()
        if "operationId" in operation
    }

    assert operation_ids == {
        "informacoes_obter",
        "saude_verificar",
        "auth_registrar",
        "auth_login",
        "auth_usuario_atual",
        "ocorrencias_listar",
        "ocorrencias_criar",
        "ocorrencias_consultar",
        "ocorrencias_atualizar",
        "ocorrencias_excluir",
        "estatisticas_obter",
    }


def test_openapi_usa_paginacao_e_patch(client):
    schema = client.get("/openapi.json").json()
    caminho = schema["paths"]["/api/v1/ocorrencias"]

    assert "get" in caminho
    assert "post" in caminho

    detalhe = schema["paths"]["/api/v1/ocorrencias/{ocorrencia_id}"]
    assert "patch" in detalhe
    assert "put" not in detalhe

    resposta = caminho["get"]["responses"]["200"]
    ref = resposta["content"]["application/json"]["schema"]["$ref"]
    nome_schema = ref.rsplit("/", 1)[-1]
    propriedades = schema["components"]["schemas"][nome_schema]["properties"]

    assert set(propriedades) == {
        "items",
        "total",
        "page",
        "page_size",
        "pages",
    }


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
    assert parametros["page"]["schema"]["examples"] == [1]
    assert parametros["page_size"]["schema"]["examples"] == [20]
