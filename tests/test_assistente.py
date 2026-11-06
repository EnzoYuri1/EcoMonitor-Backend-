from types import SimpleNamespace

import pytest
import requests

from app.core.config import settings
from app.services import assistente_service

ASSISTENTE_URL = "/api/v1/assistente"
SENHA = "senhaSegura123"


@pytest.fixture(autouse=True)
def limites_limpados():
    """Garante isolamento do controle de uso em memória entre testes."""
    assistente_service.reiniciar_limites()
    yield
    assistente_service.reiniciar_limites()


def _autenticar(client, email: str) -> dict[str, str]:
    registro = client.post(
        "/api/v1/auth/register",
        json={"nome": "Analista Teste", "email": email, "senha": SENHA},
    )
    assert registro.status_code == 201

    login = client.post(
        "/api/v1/auth/login",
        json={"email": email, "senha": SENHA},
    )
    assert login.status_code == 200
    return {"Authorization": f"Bearer {login.json()['access_token']}"}


def _resposta_openrouter(texto: str, status_code: int = 200):
    payload = (
        {"choices": [{"message": {"content": texto}}]}
        if status_code == 200
        else {"error": {"message": "erro simulado"}}
    )
    return SimpleNamespace(status_code=status_code, json=lambda: payload)


def _testar_historico(client, headers):
    perguntas = [
        "Primeira pergunta sobre o EcoMonitor.",
        "Segunda pergunta sobre o EcoMonitor.",
    ]
    for pergunta in perguntas:
        response = client.post(
            ASSISTENTE_URL,
            json={"mensagem": pergunta},
            headers=headers,
        )
        assert response.status_code == 200
    return perguntas


def test_instrucao_sistema_tem_tom_estilo():
    """O prompt do sistema mantém as regras de tom definidas no projeto."""
    texto = assistente_service._INSTRUCAO_SISTEMA

    assert "Tom e estilo" in texto
    assert "acolhedor" in texto.lower()
    assert "emoji" in texto.lower()
    assert "193" in texto
    assert "TODAS as respostas" in texto
    assert "Linguagem do usuário" in texto
    assert "backend" in texto.lower()
    assert "Recusas" in texto
    assert "no máximo 3 frases" in texto


def test_assistente_responde_com_contexto(monkeypatch, client):
    headers = _autenticar(client, "analista@example.com")

    capturado = {}

    def fake_post(url, headers=None, json=None, timeout=None):
        capturado["url"] = url
        capturado["cabecalhos"] = headers
        capturado["json"] = json
        capturado["timeout"] = timeout
        return _resposta_openrouter(
            "Acesse 'Nova ocorrência' no menu e preencha o formulário."
        )

    monkeypatch.setattr(assistente_service.requests, "post", fake_post)

    response = client.post(
        ASSISTENTE_URL,
        json={
            "mensagem": "Como cadastro uma queimada?",
            "historico": [
                {"role": "user", "content": "O que é o EcoMonitor?"},
                {"role": "assistant", "content": "Um sistema de monitoramento ambiental."},
            ],
        },
        headers=headers,
    )

    assert response.status_code == 200
    data = response.json()
    assert data["resposta"] == (
        "Acesse 'Nova ocorrência' no menu e preencha o formulário."
    )
    assert data["modelo"] == settings.OPENROUTER_MODEL

    assert capturado["url"] == assistente_service.OPENROUTER_URL
    assert capturado["cabecalhos"]["Authorization"].startswith("Bearer ")
    assert capturado["json"]["model"] == settings.OPENROUTER_MODEL
    assert capturado["json"]["temperature"] == (
        assistente_service.TEMPERATURA_ASSISTENTE
    )

    mensagens = capturado["json"]["messages"]
    assert mensagens[0]["role"] == "system"
    assert "CONHECIMENTO DO PROJETO" in mensagens[0]["content"]
    assert "RELATÓRIO DE ESTATÍSTICAS" in mensagens[0]["content"]
    assert mensagens[1] == {
        "role": "user",
        "content": "O que é o EcoMonitor?",
    }
    assert mensagens[2] == {
        "role": "assistant",
        "content": "Um sistema de monitoramento ambiental.",
    }
    assert mensagens[-1]["content"] == "Como cadastro uma queimada?"


def test_assistente_exige_autenticacao(client):
    response = client.post(ASSISTENTE_URL, json={"mensagem": "Ola"})

    assert response.status_code == 401


def test_assistente_valida_mensagem(client, monkeypatch):
    headers = _autenticar(client, "analista@example.com")
    monkeypatch.setattr(
        assistente_service.requests, "post", lambda *a, **k: _resposta_openrouter("ok")
    )

    vazio = client.post(
        ASSISTENTE_URL, json={"mensagem": "   "}, headers=headers
    )
    assert vazio.status_code == 422

    longa = client.post(
        ASSISTENTE_URL,
        json={"mensagem": "a" * 1001},
        headers=headers,
    )
    assert longa.status_code == 422


def test_assistente_valida_historico(client, monkeypatch):
    headers = _autenticar(client, "analista@example.com")
    monkeypatch.setattr(
        assistente_service.requests, "post", lambda *a, **k: _resposta_openrouter("ok")
    )

    sete_mensagens = [
        {"role": "user", "content": f"Mensagem {i}"}
        for i in range(7)
    ]
    muitos = client.post(
        ASSISTENTE_URL,
        json={"mensagem": "Pergunta válida", "historico": sete_mensagens},
        headers=headers,
    )
    assert muitos.status_code == 422

    papel_invalido = client.post(
        ASSISTENTE_URL,
        json={
            "mensagem": "Pergunta válida",
            "historico": [{"role": "system", "content": "teste"}],
        },
        headers=headers,
    )
    assert papel_invalido.status_code == 422


def test_assistente_sem_chave_configurada(monkeypatch, client):
    headers = _autenticar(client, "analista@example.com")
    monkeypatch.setattr(settings, "OPENROUTER_API_KEY", "")

    def inesperado(*args, **kwargs):
        raise AssertionError("A chamada não deveria acontecer sem chave.")

    monkeypatch.setattr(assistente_service.requests, "post", inesperado)

    response = client.post(
        ASSISTENTE_URL, json={"mensagem": "O que o site faz?"}, headers=headers
    )

    assert response.status_code == 503
    assert "OPENROUTER_API_KEY" in response.json()["detail"]


def test_assistente_desativado(monkeypatch, client):
    headers = _autenticar(client, "analista@example.com")
    monkeypatch.setattr(settings, "ASSISTENTE_HABILITADO", False)

    response = client.post(
        ASSISTENTE_URL, json={"mensagem": "O que o site faz?"}, headers=headers
    )

    assert response.status_code == 503
    assert "desativado" in response.json()["detail"]


def test_assistente_timeout_do_provedor(monkeypatch, client):
    headers = _autenticar(client, "analista@example.com")

    def demora(*args, **kwargs):
        raise requests.exceptions.Timeout()

    monkeypatch.setattr(assistente_service.requests, "post", demora)

    response = client.post(
        ASSISTENTE_URL, json={"mensagem": "O que o site faz?"}, headers=headers
    )

    assert response.status_code == 503
    assert "Tente novamente" in response.json()["detail"]


def test_assistente_cota_do_provedor(monkeypatch, client):
    headers = _autenticar(client, "analista@example.com")
    monkeypatch.setattr(
        assistente_service.requests,
        "post",
        lambda *a, **k: _resposta_openrouter("", status_code=429),
    )

    response = client.post(
        ASSISTENTE_URL, json={"mensagem": "O que o site faz?"}, headers=headers
    )

    assert response.status_code == 429
    assert "OpenRouter" in response.json()["detail"]


def test_assistente_chave_invalida(monkeypatch, client):
    headers = _autenticar(client, "analista@example.com")
    monkeypatch.setattr(
        assistente_service.requests,
        "post",
        lambda *a, **k: _resposta_openrouter("", status_code=401),
    )

    response = client.post(
        ASSISTENTE_URL, json={"mensagem": "O que o site faz?"}, headers=headers
    )

    assert response.status_code == 503
    assert "chave" in response.json()["detail"].lower()


def test_assistente_resposta_vazia(monkeypatch, client):
    headers = _autenticar(client, "analista@example.com")
    monkeypatch.setattr(
        assistente_service.requests,
        "post",
        lambda *a, **k: _resposta_openrouter("   ", status_code=200),
    )

    response = client.post(
        ASSISTENTE_URL, json={"mensagem": "O que o site faz?"}, headers=headers
    )

    assert response.status_code == 502


def test_assistente_respeita_intervalo_minimo(monkeypatch, client):
    headers = _autenticar(client, "analista@example.com")
    monkeypatch.setattr(
        assistente_service.requests,
        "post",
        lambda *a, **k: _resposta_openrouter("Resposta do assistente."),
    )

    primeira = client.post(
        ASSISTENTE_URL, json={"mensagem": "Primeira pergunta"}, headers=headers
    )
    assert primeira.status_code == 200

    segunda = client.post(
        ASSISTENTE_URL, json={"mensagem": "Segunda pergunta"}, headers=headers
    )
    assert segunda.status_code == 429
    assert "Aguarde" in segunda.json()["detail"]


def test_assistente_respeita_limite_diario(monkeypatch, client):
    headers = _autenticar(client, "analista@example.com")
    monkeypatch.setattr(assistente_service, "LIMITE_DIARIO", 1)
    monkeypatch.setattr(
        assistente_service.requests,
        "post",
        lambda *a, **k: _resposta_openrouter("Resposta do assistente."),
    )

    primeira = client.post(
        ASSISTENTE_URL, json={"mensagem": "Primeira pergunta"}, headers=headers
    )
    assert primeira.status_code == 200

    segunda = client.post(
        ASSISTENTE_URL, json={"mensagem": "Segunda pergunta"}, headers=headers
    )
    assert segunda.status_code == 429
    assert "limite diário" in segunda.json()["detail"].lower()
