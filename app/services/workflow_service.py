from pathlib import Path
from uuid import uuid4

from sqlalchemy.exc import SQLAlchemyError
from sqlmodel import Session, select

from app.core.config import BASE_DIR
from app.models import (
    Ocorrencia,
    OcorrenciaAtividade,
    OcorrenciaEvidencia,
    OcorrenciaHistorico,
)

EVIDENCIAS_DIR = BASE_DIR / "data" / "evidencias"


def registrar_evento(
    session: Session,
    ocorrencia_id: int,
    ator_id: int | None,
    acao: str,
    descricao: str,
) -> None:
    session.add(
        OcorrenciaHistorico(
            ocorrencia_id=ocorrencia_id,
            ator_id=ator_id,
            acao=acao,
            descricao=descricao,
        )
    )


def obter_detalhes(session: Session, ocorrencia: Ocorrencia) -> dict:
    atividades = session.exec(
        select(OcorrenciaAtividade)
        .where(OcorrenciaAtividade.ocorrencia_id == ocorrencia.id)
        .order_by(OcorrenciaAtividade.created_at.desc())
    ).all()
    evidencias = session.exec(
        select(OcorrenciaEvidencia)
        .where(OcorrenciaEvidencia.ocorrencia_id == ocorrencia.id)
        .order_by(OcorrenciaEvidencia.created_at.desc())
    ).all()
    historico = session.exec(
        select(OcorrenciaHistorico)
        .where(OcorrenciaHistorico.ocorrencia_id == ocorrencia.id)
        .order_by(OcorrenciaHistorico.created_at.desc())
    ).all()

    return {
        **{
            nome: getattr(ocorrencia, nome)
            for nome in (
                "id",
                "tipo",
                "municipio",
                "estado",
                "descricao",
                "latitude",
                "longitude",
                "data_ocorrencia",
                "created_by",
                "status",
                "prioridade",
                "prazo",
                "responsavel_id",
                "resolucao",
                "observacao_validacao",
                "created_at",
            )
        },
        "atividades": atividades,
        "evidencias": evidencias,
        "historico": historico,
    }


def adicionar_atividade(
    session: Session,
    ocorrencia: Ocorrencia,
    ator_id: int,
    titulo: str,
    descricao: str | None,
) -> OcorrenciaAtividade:
    atividade = OcorrenciaAtividade(
        ocorrencia_id=ocorrencia.id,
        created_by=ator_id,
        titulo=titulo,
        descricao=descricao,
    )
    session.add(atividade)
    registrar_evento(
        session,
        ocorrencia.id,
        ator_id,
        "atividade_adicionada",
        f"Atividade adicionada: {titulo}.",
    )
    session.commit()
    session.refresh(atividade)
    return atividade


def salvar_evidencia(
    session: Session,
    ocorrencia: Ocorrencia,
    ator_id: int,
    categoria: str,
    nome_arquivo: str,
    tipo_mime: str,
    conteudo: bytes,
) -> OcorrenciaEvidencia:
    extensao = Path(nome_arquivo.replace("\\", "/")).suffix.lower()
    arquivo_salvo = f"{uuid4().hex}{extensao}"
    EVIDENCIAS_DIR.mkdir(parents=True, exist_ok=True)
    destino = EVIDENCIAS_DIR / arquivo_salvo
    destino.write_bytes(conteudo)

    evidencia = OcorrenciaEvidencia(
        ocorrencia_id=ocorrencia.id,
        categoria=categoria,
        nome_arquivo=Path(nome_arquivo.replace("\\", "/")).name,
        arquivo_salvo=arquivo_salvo,
        tipo_mime=tipo_mime,
        tamanho=len(conteudo),
        enviado_por=ator_id,
    )
    session.add(evidencia)
    registrar_evento(
        session,
        ocorrencia.id,
        ator_id,
        "evidencia_adicionada",
        f"Documento anexado ({categoria}): {evidencia.nome_arquivo}.",
    )

    try:
        session.commit()
    except SQLAlchemyError:
        session.rollback()
        destino.unlink(missing_ok=True)
        raise

    session.refresh(evidencia)
    return evidencia

