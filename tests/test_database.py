from datetime import date

import pytest
from sqlalchemy.exc import IntegrityError, StatementError
from sqlmodel import SQLModel

from app.models import Ocorrencia, TipoOcorrencia, User


def _make_user(email: str = "teste@example.com") -> User:
    return User(nome="Usuário Teste", email=email, senha_hash="hash-de-teste")


def _make_ocorrencia(created_by: int) -> Ocorrencia:
    return Ocorrencia(
        tipo=TipoOcorrencia.QUEIMADA,
        municipio="Sinop",
        estado="MT",
        descricao="Foco de queimada identificado.",
        latitude=-11.8642,
        longitude=-55.5025,
        data_ocorrencia=date(2026, 10, 1),
        created_by=created_by,
    )


def test_tabelas_registradas():
    assert set(SQLModel.metadata.tables) == {
        "users",
        "ocorrencias",
        "ocorrencia_atividades",
        "ocorrencia_evidencias",
        "ocorrencia_historico",
    }


def test_cria_usuario_e_ocorrencia_com_relacionamento(session):
    user = _make_user()
    session.add(user)
    session.commit()
    session.refresh(user)

    ocorrencia = _make_ocorrencia(created_by=user.id)
    session.add(ocorrencia)
    session.commit()
    session.refresh(ocorrencia)

    assert ocorrencia.id is not None
    assert ocorrencia.tipo == TipoOcorrencia.QUEIMADA
    assert ocorrencia.owner is not None
    assert ocorrencia.owner.email == user.email

    session.refresh(user)
    assert len(user.ocorrencias) == 1
    assert user.ocorrencias[0].municipio == "Sinop"


def test_email_duplicado_e_rejeitado(session):
    session.add(_make_user())
    session.commit()

    with pytest.raises(IntegrityError):
        session.add(_make_user())
        session.commit()


def test_tipo_invalido_e_rejeitado(session):
    user = _make_user()
    session.add(user)
    session.commit()
    session.refresh(user)

    ocorrencia = Ocorrencia(
        tipo="desmatamento_ilegal",
        municipio="Sinop",
        estado="MT",
        descricao="Tipo inválido.",
        data_ocorrencia=date(2026, 10, 1),
        created_by=user.id,
    )
    session.add(ocorrencia)
    with pytest.raises(StatementError):
        session.commit()
