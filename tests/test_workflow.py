from datetime import date, timedelta

from sqlmodel import select

from app.models import User
from app.services import workflow_service

BASE = "/api/v1"
OCORRENCIAS = f"{BASE}/ocorrencias"
SENHA = "senhaSegura123"


def _criar_usuario(client, email: str) -> dict[str, str]:
    resposta = client.post(
        f"{BASE}/auth/register",
        json={"nome": email.split("@")[0], "email": email, "senha": SENHA},
    )
    assert resposta.status_code == 201
    token = client.post(
        f"{BASE}/auth/login",
        json={"email": email, "senha": SENHA},
    ).json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def _criar_ocorrencia(client, headers) -> dict:
    resposta = client.post(
        OCORRENCIAS,
        headers=headers,
        json={
            "tipo": "queimada",
            "municipio": "Sinop",
            "estado": "MT",
            "descricao": "Foco de queimada na região rural.",
            "data_ocorrencia": date.today().isoformat(),
        },
    )
    assert resposta.status_code == 201
    return resposta.json()


def _enviar_arquivo(client, headers, ocorrencia_id, categoria, arquivo):
    return client.post(
        f"{OCORRENCIAS}/{ocorrencia_id}/evidencias",
        headers=headers,
        data={"categoria": categoria},
        files={"arquivo": arquivo},
    )


def test_fluxo_completo_com_permissoes_e_documentos(
    client,
    session,
    tmp_path,
    monkeypatch,
):
    monkeypatch.setattr(workflow_service, "EVIDENCIAS_DIR", tmp_path)
    owner = _criar_usuario(client, "autor@example.com")
    executor = _criar_usuario(client, "executor@example.com")
    admin = _criar_usuario(client, "admin@example.com")

    usuario_admin = session.exec(
        select(User).where(User.email == "admin@example.com")
    ).one()
    usuario_admin.perfil = "administrador"
    session.add(usuario_admin)
    session.commit()

    ocorrencia = _criar_ocorrencia(client, owner)
    ocorrencia_id = ocorrencia["id"]
    triagem = {
        "prioridade": "alta",
        "prazo": (date.today() + timedelta(days=5)).isoformat(),
        "responsavel_id": session.exec(
            select(User.id).where(User.email == "executor@example.com")
        ).one(),
    }

    sem_evidencia = client.patch(
        f"{OCORRENCIAS}/{ocorrencia_id}/triagem",
        headers=admin,
        json=triagem,
    )
    assert sem_evidencia.status_code == 409

    inicial = _enviar_arquivo(
        client,
        owner,
        ocorrencia_id,
        "inicial",
        ("inicial.png", b"\x89PNG\r\n\x1a\nconteudo", "image/png"),
    )
    assert inicial.status_code == 201
    assert inicial.json()["categoria"] == "inicial"

    triada = client.patch(
        f"{OCORRENCIAS}/{ocorrencia_id}/triagem",
        headers=admin,
        json=triagem,
    )
    assert triada.status_code == 200
    assert triada.json()["status"] == "em_execucao"
    assert triada.json()["responsavel_id"] == triagem["responsavel_id"]

    negada = client.post(
        f"{OCORRENCIAS}/{ocorrencia_id}/atividades",
        headers=owner,
        json={"titulo": "Inspecionar o perímetro"},
    )
    assert negada.status_code == 403

    atividade = client.post(
        f"{OCORRENCIAS}/{ocorrencia_id}/atividades",
        headers=executor,
        json={
            "titulo": "Inspecionar o perímetro",
            "descricao": "Verificar o local indicado.",
        },
    )
    assert atividade.status_code == 201

    sem_documento = client.post(
        f"{OCORRENCIAS}/{ocorrencia_id}/solicitar-conclusao",
        headers=executor,
        json={"resolucao": "Inspeção realizada e área isolada."},
    )
    assert sem_documento.status_code == 409

    conclusao = _enviar_arquivo(
        client,
        executor,
        ocorrencia_id,
        "conclusao",
        ("laudo.pdf", b"%PDF-1.7\nlaudo", "application/pdf"),
    )
    assert conclusao.status_code == 201

    documento = client.get(
        f"{OCORRENCIAS}/{ocorrencia_id}/evidencias/"
        f"{conclusao.json()['id']}/download",
        headers=executor,
    )
    assert documento.status_code == 200
    assert documento.content.startswith(b"%PDF-")

    atividade_atualizada = client.patch(
        f"{OCORRENCIAS}/{ocorrencia_id}/atividades/"
        f"{atividade.json()['id']}",
        headers=executor,
        json={"concluida": True},
    )
    assert atividade_atualizada.status_code == 200
    assert atividade_atualizada.json()["concluida"] is True

    solicitacao = client.post(
        f"{OCORRENCIAS}/{ocorrencia_id}/solicitar-conclusao",
        headers=executor,
        json={"resolucao": "Inspeção realizada e área isolada."},
    )
    assert solicitacao.status_code == 200
    assert solicitacao.json()["status"] == "em_validacao"

    sem_motivo = client.post(
        f"{OCORRENCIAS}/{ocorrencia_id}/validar-conclusao",
        headers=admin,
        json={"aprovado": False},
    )
    assert sem_motivo.status_code == 422

    devolvida = client.post(
        f"{OCORRENCIAS}/{ocorrencia_id}/validar-conclusao",
        headers=admin,
        json={"aprovado": False, "comentario": "Anexe o laudo assinado."},
    )
    assert devolvida.status_code == 200
    assert devolvida.json()["status"] == "em_execucao"

    solicitacao = client.post(
        f"{OCORRENCIAS}/{ocorrencia_id}/solicitar-conclusao",
        headers=executor,
        json={"resolucao": "Laudo assinado e área isolada."},
    )
    assert solicitacao.status_code == 200

    encerrada = client.post(
        f"{OCORRENCIAS}/{ocorrencia_id}/validar-conclusao",
        headers=admin,
        json={"aprovado": True, "comentario": "Documentos conferidos."},
    )
    assert encerrada.status_code == 200
    assert encerrada.json()["status"] == "concluida"

    detalhe = client.get(f"{OCORRENCIAS}/{ocorrencia_id}", headers=admin)
    assert detalhe.status_code == 200
    assert len(detalhe.json()["atividades"]) == 1
    assert len(detalhe.json()["evidencias"]) == 2
    assert len(detalhe.json()["historico"]) >= 7


def test_upload_rejeita_tipo_nao_permitido(client):
    headers = _criar_usuario(client, "autor@example.com")
    ocorrencia = _criar_ocorrencia(client, headers)

    resposta = _enviar_arquivo(
        client,
        headers,
        ocorrencia["id"],
        "inicial",
        ("script.svg", b"<svg></svg>", "image/svg+xml"),
    )

    assert resposta.status_code == 415
