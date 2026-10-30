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
    assert "/api/v1/auth/login" in schema["paths"]
    assert "/api/v1/ocorrencias" in schema["paths"]
    assert "/api/v1/stats" in schema["paths"]
