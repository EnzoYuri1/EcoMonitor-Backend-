from datetime import date, datetime, timezone
from pathlib import Path as FilePath
from typing import Annotated

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    Path,
    Query,
    Response,
    UploadFile,
    status,
)
from fastapi.responses import FileResponse
from sqlmodel import Session, select

from app.api.v1.responses import (
    BAD_REQUEST_RESPONSE,
    FORBIDDEN_RESPONSE,
    NOT_FOUND_RESPONSE,
    UNAUTHORIZED_RESPONSE,
    VALIDATION_ERROR_RESPONSE,
)
from app.core.config import settings
from app.core.security import get_admin_user, get_current_user
from app.db.session import get_session
from app.models import (
    Ocorrencia,
    OcorrenciaAtividade,
    OcorrenciaEvidencia,
    TipoOcorrencia,
    User,
)
from app.schemas.common import Page
from app.schemas.ocorrencia import (
    AtividadeCreate,
    AtividadeRead,
    AtividadeUpdate,
    EvidenciaRead,
    OcorrenciaDetalhe,
    OcorrenciaCreate,
    OcorrenciaRead,
    OcorrenciaUpdate,
    SolicitacaoConclusao,
    TriagemInput,
    ValidacaoConclusao,
)
from app.services import ocorrencia_service
from app.services import workflow_service

router = APIRouter(prefix="/ocorrencias", tags=["Ocorrências"])
MAX_EVIDENCIA_BYTES = 10 * 1024 * 1024
TIPOS_EVIDENCIA = {
    "image/jpeg": {".jpg", ".jpeg"},
    "image/png": {".png"},
    "application/pdf": {".pdf"},
}


def _get_or_404(session: Session, ocorrencia_id: int) -> Ocorrencia:
    ocorrencia = ocorrencia_service.get_ocorrencia(session, ocorrencia_id)
    if ocorrencia is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Ocorrência não encontrada.",
        )
    return ocorrencia


def _check_owner(ocorrencia: Ocorrencia, user_id: int) -> None:
    if ocorrencia.created_by != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Somente o autor pode alterar ou excluir esta ocorrência.",
        )


def _check_view_access(ocorrencia: Ocorrencia, user: User) -> None:
    if user.perfil == "administrador":
        return
    if user.id not in (ocorrencia.created_by, ocorrencia.responsavel_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Você não tem acesso a esta ocorrência.",
        )


def _check_execution_access(ocorrencia: Ocorrencia, user: User) -> None:
    if user.perfil == "administrador":
        return
    if ocorrencia.responsavel_id != user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Somente o responsável atribuído pode executar esta ação.",
        )


def _registrar_evento(
    session: Session,
    ocorrencia: Ocorrencia,
    user: User,
    acao: str,
    descricao: str,
) -> None:
    workflow_service.registrar_evento(
        session,
        ocorrencia.id,
        user.id,
        acao,
        descricao,
    )


@router.get(
    "",
    response_model=Page[OcorrenciaRead],
    operation_id="ocorrencias_listar",
    summary="Listar ocorrências",
    description=(
        "Lista ocorrências ambientais de forma paginada. Todos os filtros "
        "são opcionais e podem ser combinados. O período é inclusivo.\n\n"
        "**Exemplo:** `GET /api/v1/ocorrencias?tipo=queimada&municipio=sin"
        "&page=1&page_size=20`"
    ),
    response_description="Página de ocorrências encontradas.",
    responses={
        400: BAD_REQUEST_RESPONSE,
        401: UNAUTHORIZED_RESPONSE,
        422: VALIDATION_ERROR_RESPONSE,
    },
)
def list_ocorrencias(
    tipo: TipoOcorrencia | None = Query(
        default=None,
        description="Filtrar por queimada ou desmatamento.",
        examples=["queimada"],
    ),
    municipio: str | None = Query(
        default=None,
        min_length=1,
        max_length=120,
        description="Busca parcial por município, sem diferenciar maiúsculas.",
        examples=["Sinop"],
    ),
    data_inicio: date | None = Query(
        default=None,
        description="Data inicial do período (AAAA-MM-DD), inclusive.",
        examples=["2026-10-01"],
    ),
    data_fim: date | None = Query(
        default=None,
        description="Data final do período (AAAA-MM-DD), inclusive.",
        examples=["2026-10-31"],
    ),
    page: int = Query(
        default=1,
        ge=1,
        description="Número da página, começando em 1.",
        examples=[1],
    ),
    page_size: int = Query(
        default=20,
        ge=1,
        le=100,
        description="Quantidade de itens por página (1 a 100).",
        examples=[20],
    ),
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> Page[OcorrenciaRead]:
    if data_inicio and data_fim and data_inicio > data_fim:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A data inicial não pode ser posterior à data final.",
        )

    ocorrencias, total = ocorrencia_service.list_ocorrencias(
        session,
        tipo=tipo,
        municipio=municipio,
        data_inicio=data_inicio,
        data_fim=data_fim,
        page=page,
        page_size=page_size,
        current_user=current_user,
    )
    return Page[OcorrenciaRead](
        items=ocorrencias,
        total=total,
        page=page,
        page_size=page_size,
        pages=(total + page_size - 1) // page_size,
    )


@router.post(
    "",
    response_model=OcorrenciaRead,
    status_code=status.HTTP_201_CREATED,
    operation_id="ocorrencias_criar",
    summary="Cadastrar ocorrência",
    description=(
        "Registra uma nova ocorrência vinculada automaticamente ao usuário "
        "autenticado.\n\n"
        "O campo `created_by` é definido pelo token e não deve ser enviado "
        "no corpo da requisição."
    ),
    response_description="Ocorrência cadastrada com sucesso.",
    responses={
        401: UNAUTHORIZED_RESPONSE,
        422: VALIDATION_ERROR_RESPONSE,
    },
)
def create_ocorrencia(
    ocorrencia_in: OcorrenciaCreate,
    response: Response,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> Ocorrencia:
    ocorrencia = ocorrencia_service.create_ocorrencia(
        session,
        ocorrencia_in,
        current_user.id,
    )
    response.headers["Location"] = (
        f"{settings.API_V1_STR}/ocorrencias/{ocorrencia.id}"
    )
    return ocorrencia


@router.get(
    "/{ocorrencia_id}",
    response_model=OcorrenciaDetalhe,
    operation_id="ocorrencias_consultar",
    summary="Consultar ocorrência",
    description="Retorna uma ocorrência específica pelo identificador.",
    response_description="Ocorrência encontrada.",
    responses={
        401: UNAUTHORIZED_RESPONSE,
        404: NOT_FOUND_RESPONSE,
        422: VALIDATION_ERROR_RESPONSE,
    },
)
def get_ocorrencia(
    ocorrencia_id: Annotated[int, Path(description="ID da ocorrência.")],
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> dict:
    ocorrencia = _get_or_404(session, ocorrencia_id)
    _check_view_access(ocorrencia, current_user)
    return workflow_service.obter_detalhes(session, ocorrencia)


@router.patch(
    "/{ocorrencia_id}",
    response_model=OcorrenciaRead,
    operation_id="ocorrencias_atualizar",
    summary="Atualizar ocorrência",
    description=(
        "Atualiza parcialmente uma ocorrência. Envie apenas os campos que "
        "deseja alterar; os demais permanecem inalterados.\n\n"
        "Somente o usuário responsável pode executar esta operação. Campos "
        "obrigatórios não podem ser anulados."
    ),
    response_description="Ocorrência atualizada com sucesso.",
    responses={
        401: UNAUTHORIZED_RESPONSE,
        403: FORBIDDEN_RESPONSE,
        404: NOT_FOUND_RESPONSE,
        422: VALIDATION_ERROR_RESPONSE,
    },
)
def update_ocorrencia(
    ocorrencia_id: Annotated[int, Path(description="ID da ocorrência.")],
    ocorrencia_in: OcorrenciaUpdate,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> Ocorrencia:
    ocorrencia = _get_or_404(session, ocorrencia_id)
    if current_user.perfil != "administrador":
        _check_owner(ocorrencia, current_user.id)
        if ocorrencia.status != "registrada":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="O registro só pode ser editado antes da triagem.",
            )
    return ocorrencia_service.update_ocorrencia(
        session,
        ocorrencia,
        ocorrencia_in,
    )


@router.delete(
    "/{ocorrencia_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    operation_id="ocorrencias_excluir",
    summary="Excluir ocorrência",
    description="Remove uma ocorrência. Somente o responsável pode excluir.",
    response_description="Ocorrência excluída com sucesso.",
    responses={
        401: UNAUTHORIZED_RESPONSE,
        403: FORBIDDEN_RESPONSE,
        404: NOT_FOUND_RESPONSE,
        422: VALIDATION_ERROR_RESPONSE,
    },
)
def delete_ocorrencia(
    ocorrencia_id: Annotated[int, Path(description="ID da ocorrência.")],
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> None:
    ocorrencia = _get_or_404(session, ocorrencia_id)
    if current_user.perfil != "administrador":
        _check_owner(ocorrencia, current_user.id)
        if ocorrencia.status != "registrada":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="O registro só pode ser excluído antes da triagem.",
            )
    ocorrencia_service.delete_ocorrencia(session, ocorrencia)


@router.patch(
    "/{ocorrencia_id}/triagem",
    response_model=OcorrenciaRead,
    operation_id="ocorrencias_triagem",
    summary="Definir prioridade, prazo e responsável",
    responses={401: UNAUTHORIZED_RESPONSE, 403: FORBIDDEN_RESPONSE},
)
def triar_ocorrencia(
    ocorrencia_id: Annotated[int, Path(description="ID da ocorrência.")],
    triagem: TriagemInput,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_admin_user),
) -> Ocorrencia:
    ocorrencia = _get_or_404(session, ocorrencia_id)
    if ocorrencia.status not in ("registrada", "em_execucao"):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A triagem só pode ser feita antes da validação documental.",
        )
    if triagem.prazo < date.today():
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="O prazo não pode estar no passado.",
        )
    responsavel = session.get(User, triagem.responsavel_id)
    if responsavel is None or responsavel.perfil != "funcionario":
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Selecione um funcionário ativo como responsável.",
        )
    evidencias_iniciais = session.exec(
        select(OcorrenciaEvidencia).where(
            OcorrenciaEvidencia.ocorrencia_id == ocorrencia.id,
            OcorrenciaEvidencia.categoria == "inicial",
        )
    ).first()
    if evidencias_iniciais is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Anexe ao menos uma evidência inicial antes da triagem.",
        )

    ocorrencia.prioridade = triagem.prioridade
    ocorrencia.prazo = triagem.prazo
    ocorrencia.responsavel_id = triagem.responsavel_id
    ocorrencia.status = "em_execucao"
    ocorrencia.observacao_validacao = None
    session.add(ocorrencia)
    _registrar_evento(
        session,
        ocorrencia,
        current_user,
        "triagem",
        (
            f"Triagem concluída: prioridade {triagem.prioridade}, prazo "
            f"{triagem.prazo.isoformat()} e responsável {responsavel.nome}."
        ),
    )
    session.commit()
    session.refresh(ocorrencia)
    return ocorrencia


@router.post(
    "/{ocorrencia_id}/atividades",
    response_model=AtividadeRead,
    status_code=status.HTTP_201_CREATED,
    operation_id="ocorrencias_atividade_criar",
    summary="Registrar atividade",
)
def criar_atividade(
    ocorrencia_id: Annotated[int, Path(description="ID da ocorrência.")],
    dados: AtividadeCreate,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> OcorrenciaAtividade:
    ocorrencia = _get_or_404(session, ocorrencia_id)
    _check_view_access(ocorrencia, current_user)
    _check_execution_access(ocorrencia, current_user)
    if ocorrencia.status != "em_execucao":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="As atividades só podem ser registradas durante a execução.",
        )
    return workflow_service.adicionar_atividade(
        session,
        ocorrencia,
        current_user.id,
        dados.titulo,
        dados.descricao,
    )


@router.patch(
    "/{ocorrencia_id}/atividades/{atividade_id}",
    response_model=AtividadeRead,
    operation_id="ocorrencias_atividade_atualizar",
    summary="Atualizar atividade",
)
def atualizar_atividade(
    ocorrencia_id: Annotated[int, Path(description="ID da ocorrência.")],
    atividade_id: Annotated[int, Path(description="ID da atividade.")],
    dados: AtividadeUpdate,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> OcorrenciaAtividade:
    ocorrencia = _get_or_404(session, ocorrencia_id)
    _check_view_access(ocorrencia, current_user)
    _check_execution_access(ocorrencia, current_user)
    if ocorrencia.status != "em_execucao":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="As atividades só podem ser alteradas durante a execução.",
        )
    atividade = session.get(OcorrenciaAtividade, atividade_id)
    if atividade is None or atividade.ocorrencia_id != ocorrencia.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Atividade não encontrada.",
        )
    atividade.concluida = dados.concluida
    atividade.concluida_em = (
        datetime.now(timezone.utc) if dados.concluida else None
    )
    session.add(atividade)
    _registrar_evento(
        session,
        ocorrencia,
        current_user,
        "atividade_atualizada",
        (
            f"Atividade {'concluída' if dados.concluida else 'reaberta'}: "
            f"{atividade.titulo}."
        ),
    )
    session.commit()
    session.refresh(atividade)
    return atividade


@router.post(
    "/{ocorrencia_id}/evidencias",
    response_model=EvidenciaRead,
    status_code=status.HTTP_201_CREATED,
    operation_id="ocorrencias_evidencia_enviar",
    summary="Enviar evidência ou documento",
)
async def enviar_evidencia(
    ocorrencia_id: Annotated[int, Path(description="ID da ocorrência.")],
    categoria: Annotated[str, Form()],
    arquivo: Annotated[UploadFile, File()],
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> OcorrenciaEvidencia:
    ocorrencia = _get_or_404(session, ocorrencia_id)
    _check_view_access(ocorrencia, current_user)
    if categoria not in {"inicial", "execucao", "conclusao"}:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Categoria de documento inválida.",
        )

    if current_user.perfil != "administrador":
        if categoria == "inicial":
            _check_owner(ocorrencia, current_user.id)
            if ocorrencia.status != "registrada":
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Evidências iniciais só podem ser enviadas antes da triagem.",
                )
        else:
            _check_execution_access(ocorrencia, current_user)
            if ocorrencia.status != "em_execucao":
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Documentos de execução só podem ser enviados durante a execução.",
                )

    tipo_mime = (arquivo.content_type or "").lower()
    extensao = FilePath(
        (arquivo.filename or "").replace("\\", "/")
    ).suffix.lower()
    if extensao not in TIPOS_EVIDENCIA.get(tipo_mime, set()):
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="Envie apenas arquivos PDF, JPG ou PNG válidos.",
        )
    conteudo = await arquivo.read(MAX_EVIDENCIA_BYTES + 1)
    if len(conteudo) > MAX_EVIDENCIA_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="Cada arquivo deve ter no máximo 10 MB.",
        )
    if not conteudo:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="O arquivo enviado está vazio.",
        )
    assinaturas_validas = {
        "application/pdf": conteudo.startswith(b"%PDF-"),
        "image/jpeg": conteudo.startswith(b"\xff\xd8\xff"),
        "image/png": conteudo.startswith(b"\x89PNG\r\n\x1a\n"),
    }
    if not assinaturas_validas.get(tipo_mime, False):
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="O conteúdo do arquivo não corresponde ao formato informado.",
        )

    return workflow_service.salvar_evidencia(
        session,
        ocorrencia,
        current_user.id,
        categoria,
        arquivo.filename or "documento",
        tipo_mime,
        conteudo,
    )


@router.get(
    "/{ocorrencia_id}/evidencias/{evidencia_id}/download",
    operation_id="ocorrencias_evidencia_baixar",
    summary="Baixar evidência ou documento",
)
def baixar_evidencia(
    ocorrencia_id: Annotated[int, Path(description="ID da ocorrência.")],
    evidencia_id: Annotated[int, Path(description="ID do documento.")],
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> FileResponse:
    ocorrencia = _get_or_404(session, ocorrencia_id)
    _check_view_access(ocorrencia, current_user)
    evidencia = session.get(OcorrenciaEvidencia, evidencia_id)
    if evidencia is None or evidencia.ocorrencia_id != ocorrencia.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Documento não encontrado.",
        )
    caminho = workflow_service.EVIDENCIAS_DIR / evidencia.arquivo_salvo
    if not caminho.is_file():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="O arquivo armazenado não está disponível.",
        )
    return FileResponse(
        caminho,
        media_type=evidencia.tipo_mime,
        filename=evidencia.nome_arquivo,
    )


@router.post(
    "/{ocorrencia_id}/solicitar-conclusao",
    response_model=OcorrenciaRead,
    operation_id="ocorrencias_solicitar_conclusao",
    summary="Solicitar conclusão da ocorrência",
)
def solicitar_conclusao(
    ocorrencia_id: Annotated[int, Path(description="ID da ocorrência.")],
    dados: SolicitacaoConclusao,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> Ocorrencia:
    ocorrencia = _get_or_404(session, ocorrencia_id)
    _check_view_access(ocorrencia, current_user)
    _check_execution_access(ocorrencia, current_user)
    if ocorrencia.status != "em_execucao":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A ocorrência não está em execução.",
        )
    atividades_pendentes = session.exec(
        select(OcorrenciaAtividade).where(
            OcorrenciaAtividade.ocorrencia_id == ocorrencia.id,
            OcorrenciaAtividade.concluida.is_(False),
        )
    ).first()
    if atividades_pendentes is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Conclua todas as atividades antes de solicitar o encerramento.",
        )
    documento_final = session.exec(
        select(OcorrenciaEvidencia).where(
            OcorrenciaEvidencia.ocorrencia_id == ocorrencia.id,
            OcorrenciaEvidencia.categoria == "conclusao",
        )
    ).first()
    if documento_final is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Anexe ao menos um documento comprobatório de conclusão.",
        )
    ocorrencia.resolucao = dados.resolucao
    ocorrencia.observacao_validacao = None
    ocorrencia.status = "em_validacao"
    session.add(ocorrencia)
    _registrar_evento(
        session,
        ocorrencia,
        current_user,
        "conclusao_solicitada",
        "Responsável solicitou a conclusão e enviou a resolução para validação.",
    )
    session.commit()
    session.refresh(ocorrencia)
    return ocorrencia


@router.post(
    "/{ocorrencia_id}/validar-conclusao",
    response_model=OcorrenciaRead,
    operation_id="ocorrencias_validar_conclusao",
    summary="Aprovar ou devolver para ajustes",
)
def validar_conclusao(
    ocorrencia_id: Annotated[int, Path(description="ID da ocorrência.")],
    dados: ValidacaoConclusao,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_admin_user),
) -> Ocorrencia:
    ocorrencia = _get_or_404(session, ocorrencia_id)
    if ocorrencia.status != "em_validacao":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A ocorrência não está aguardando validação documental.",
        )
    if not dados.aprovado and not (dados.comentario or "").strip():
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Informe o motivo da devolução para ajustes.",
        )

    if dados.aprovado:
        ocorrencia.status = "concluida"
        ocorrencia.observacao_validacao = dados.comentario
        acao = "conclusao_aprovada"
        descricao = "Documentos aprovados; ocorrência oficialmente concluída."
    else:
        ocorrencia.status = "em_execucao"
        ocorrencia.observacao_validacao = dados.comentario
        acao = "conclusao_devolvida"
        descricao = f"Documentação devolvida para ajustes: {dados.comentario}"

    session.add(ocorrencia)
    _registrar_evento(
        session,
        ocorrencia,
        current_user,
        acao,
        descricao,
    )
    session.commit()
    session.refresh(ocorrencia)
    return ocorrencia
