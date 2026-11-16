from datetime import timedelta

from sqlmodel import select

from app.core.security import create_access_token
from app.models import User

EMAIL = "maria@example.com"
SENHA = "senhaSegura123"


def _register(client, email: str = EMAIL, senha: str = SENHA):
    return client.post(
        "/api/v1/auth/register",
        json={"nome": "Maria Silva", "email": email, "senha": senha},
    )


def _login(client, email: str = EMAIL, senha: str = SENHA):
    return client.post(
        "/api/v1/auth/login",
        json={"email": email, "senha": senha},
    )


def _auth_header(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def test_registro_de_usuario(client, session):
    response = _register(client)

    assert response.status_code == 201
    data = response.json()
    assert data["nome"] == "Maria Silva"
    assert data["email"] == EMAIL
    assert data["perfil"] == "funcionario"
    assert data["id"] > 0
    assert "senha" not in data
    assert "senha_hash" not in data

    user = session.exec(select(User).where(User.email == EMAIL)).first()
    assert user is not None
    assert user.senha_hash != SENHA
    assert user.senha_hash.startswith("$2")


def test_email_duplicado_e_rejeitado(client):
    assert _register(client).status_code == 201

    response = _register(client, email="MARIA@EXAMPLE.COM")

    assert response.status_code == 409
    assert response.json()["detail"] == "Email já cadastrado."


def test_login_retorna_token(client):
    _register(client)

    response = _login(client)

    assert response.status_code == 200
    data = response.json()
    assert data["token_type"] == "bearer"
    assert data["access_token"]
    assert data["expires_in"] == 3600


def test_login_com_senha_incorreta(client):
    _register(client)

    response = _login(client, senha="senhaErrada123")

    assert response.status_code == 401
    assert response.json()["detail"] == "Email ou senha incorretos."


def test_login_com_email_inexistente(client):
    response = _login(client, email="naoexiste@example.com")

    assert response.status_code == 401
    assert response.json()["detail"] == "Email ou senha incorretos."


def test_me_com_token_valido(client):
    _register(client)
    token = _login(client).json()["access_token"]

    response = client.get("/api/v1/auth/me", headers=_auth_header(token))

    assert response.status_code == 200
    assert response.json()["email"] == EMAIL


def test_me_sem_token(client):
    response = client.get("/api/v1/auth/me")

    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"


def test_me_com_token_invalido(client):
    response = client.get(
        "/api/v1/auth/me",
        headers=_auth_header("token-invalido"),
    )

    assert response.status_code == 401


def test_me_com_token_expirado(client):
    _register(client)
    token = create_access_token(1, expires_delta=timedelta(seconds=-1))

    response = client.get("/api/v1/auth/me", headers=_auth_header(token))

    assert response.status_code == 401


def test_me_com_usuario_inexistente(client):
    token = create_access_token(9999)

    response = client.get("/api/v1/auth/me", headers=_auth_header(token))

    assert response.status_code == 401


def test_listagem_de_usuarios_exige_administrador(client, session):
    _register(client)
    token = _login(client).json()["access_token"]
    headers = _auth_header(token)

    proibido = client.get("/api/v1/auth/users", headers=headers)
    assert proibido.status_code == 403

    user = session.exec(select(User).where(User.email == EMAIL)).first()
    user.perfil = "administrador"
    session.add(user)
    session.commit()

    permitido = client.get("/api/v1/auth/users", headers=headers)
    assert permitido.status_code == 200
    assert permitido.json()[0]["perfil"] == "administrador"


def test_validacao_dos_campos_de_registro(client):
    response = client.post(
        "/api/v1/auth/register",
        json={"nome": "M", "email": "email-invalido", "senha": "123"},
    )

    assert response.status_code == 422
