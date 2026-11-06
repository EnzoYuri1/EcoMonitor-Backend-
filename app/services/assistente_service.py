"""Integração do assistente de dúvidas com o OpenRouter.

O serviço monta o contexto da conversa (guia do analista + estatísticas
agregadas do banco), envia a pergunta para a API compatível com OpenAI do
OpenRouter e traduz os erros para mensagens amigáveis em português.

Nenhuma descrição de ocorrência ou dado pessoal do usuário é enviada ao
provedor: apenas a pergunta, o histórico curto e estatísticas agregadas.
"""

import time
from datetime import date
from pathlib import Path

import requests
from fastapi import HTTPException, status
from sqlmodel import Session

from app.core.config import settings
from app.schemas.assistente import (
    HISTORICO_MAX_MENSAGENS,
    AssistenteRequest,
)
from app.schemas.stats import StatsRead
from app.services import stats_service

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"

GUIA_PATH = Path(__file__).resolve().parents[2] / "docs" / "GUIA_ANALISTA.md"

# Controle simples de uso por usuário (em memória). Protegem a cota gratuita
# do OpenRouter (50 requisições/dia) sem depender de infraestrutura externa.
INTERVALO_MINIMO_SEGUNDOS = 3
LIMITE_DIARIO = 40

# Tom um pouco mais natural nas respostas do modelo gratuito.
TEMPERATURA_ASSISTENTE = 0.7

_ultimo_envio: dict[int, float] = {}
_envios_do_dia: dict[int, tuple[str, int]] = {}

_guia_cacheado: str | None = None

_INSTRUCAO_SISTEMA = (
    "Você é o Assistente EcoMonitor e atende analistas ambientais dentro da "
    "aplicação web EcoMonitor.\n"
    "Regras obrigatórias (precisão e segurança):\n"
    "- Responda sempre em português do Brasil.\n"
    "- Baseie suas respostas apenas no CONHECIMENTO DO PROJETO e no RELATÓRIO "
    "DE ESTATÍSTICAS informados. Não invente funcionalidades, campos, "
    "endpoints ou números.\n"
    "- Você pode explicar qualquer parte do EcoMonitor: telas, cadastro, "
    "consulta, edição, exclusão, significado dos campos, regras de "
    "validação, permissões, dashboard, mapa e relatórios.\n"
    "- Quando citar números do banco, deixe claro que vêm do relatório de "
    "estatísticas incluído nesta conversa.\n"
    "- Você não executa ações: nunca diga que criou, editou ou excluiu "
    "algo; apenas oriente o usuário passo a passo na interface.\n"
    "- Se a pergunta fugir do EcoMonitor ou do trabalho do analista "
    "ambiental, avise com educação que só responde sobre o sistema.\n"
    "- Você orienta, mas não substitui a avaliação técnica ou legal de um "
    "profissional.\n"
    "- Se faltar informação, diga o que sabe e sugira o caminho na "
    "aplicação, sem suposições.\n"
    "\n"
    "### Linguagem do usuário — siga em TODAS as respostas:\n"
    "- Fale do ponto de vista de quem usa: telas, menus, botões, campos e "
    "passos na interface.\n"
    "- Termos técnicos de tecnologia NÃO aparecem no texto: backend, "
    "frontend, API, REST, token, JWT, Bearer, banco de dados, servidor, "
    "rede, HTTP, JSON, códigos de erro (401, 403, 404, 409, 422, 429, 500 "
    "e outros). Em vez de 'erro 403', diga 'o sistema mostra uma mensagem "
    "dizendo que você não tem permissão'. Em vez de 'token', diga 'acesso' "
    "ou 'sessão'.\n"
    "- Se o usuário perguntar como a aplicação foi construída por dentro "
    "(tecnologia, servidores, banco), responda em 1 frase simpática que "
    "isso é detalhe interno e redirecione para o uso: 'O que importa em uso "
    "é [...]'.\n"
    "\n"
    "### Recusas — siga em TODAS as respostas:\n"
    "- Perguntas maliciosas, de segurança ofensiva, 'hackear', burlar "
    "controle de acesso, testes de invasão, e também perguntas fora do "
    "EcoMonitor (política, notícias, código em geral) recebem resposta "
    "CURTA: no máximo 3 frases — recuse com gentileza, diga que sua "
    "função é orientar o uso normal do EcoMonitor e ofereça ajuda com o "
    "que faz parte do sistema.\n"
    "- Em recusas: NÃO explique nada técnico, NÃO descreva medidas de "
    "segurança, NÃO cite erros ou números de verificação e NÃO use emojis. "
    "Nunca repita o pedido e nunca 'adapte' o que foi pedido.\n"
    "\n"
    "### Tom e estilo — siga em TODAS as respostas:\n"
    "- Acolhedor, educado e levemente divertido, como um colega prestativo; "
    "nunca robotizado nem jargon demais.\n"
    "- Use no máximo 1 a 3 emojis por resposta, sempre ligados ao assunto "
    "(🔥 queimada, 🌳 desmatamento, 📝 cadastro, 📊 dashboard, 🗺️ mapa). "
    "Nunca use emoji em nomes de campos, códigos, URLs ou valores.\n"
    "- Comece com a resposta direta em 1 frase; detalhe só o necessário "
    "depois.\n"
    "- Tamanho médio: 3 a 6 blocos curtos. Pergunta simples → 1 ou 2 "
    "frases. Aprofunde apenas se o usuário pedir 'explique melhor'.\n"
    "- Use lista numerada para passos e bullets curtos para regras; evite "
    "parágrafos longos.\n"
    "- Explique termos técnicos em linguagem simples na primeira vez que "
    "aparecerem.\n"
    "- Inclua um exemplo prático quando ajudar a entender.\n"
    "- Feche com uma oferta curta de ajuda, variando a frase (ex.: 'Quer "
    "que eu detalhe algum passo?') sem repetir sempre a mesma.\n"
    "- Em tema sensível (fogo ativo, risco a pessoas ou a quem responde no "
    "campo), deixe de lado brincadeiras e emojis: oriente de forma direta "
    "a acionar o Corpo de Bombeiros (193) e o órgão ambiental competente."
)


def _carregar_guia() -> str:
    """Carrega o guia do analista do disco (uma leitura por processo)."""
    global _guia_cacheado
    if _guia_cacheado is None:
        try:
            _guia_cacheado = GUIA_PATH.read_text(encoding="utf-8").strip()
        except OSError:
            _guia_cacheado = (
                "Guia do EcoMonitor indisponível nesta instalação. "
                "Descreva as funcionalidades com base em perguntas concretas."
            )
    return _guia_cacheado


def _descrever_estatisticas(estatisticas: StatsRead) -> str:
    """Formata os indicadores agregados bloqueando listas longas."""
    top = estatisticas.por_municipio[:10]
    outros = len(estatisticas.por_municipio) - len(top)
    municipios = ", ".join(
        f"{item.municipio} ({item.total})" for item in top
    ) or "sem registros"
    tipos = ", ".join(
        f"{item.tipo.value}: {item.total}" for item in estatisticas.por_tipo
    )

    linhas = [
        f"- Total de ocorrências: {estatisticas.total_ocorrencias}",
        f"- Total de queimadas: {estatisticas.total_queimadas}",
        f"- Total de desmatamentos: {estatisticas.total_desmatamentos}",
        f"- Municípios registrados: {len(estatisticas.por_municipio)}",
        f"- Municípios com mais ocorrências: {municipios}",
    ]
    if outros > 0:
        linhas[-1] += f" (+ {outros} demais)"
    linhas.append(f"- Distribuição por tipo: {tipos or 'sem registros'}")

    return "\n".join(linhas)


def _montar_mensagens(
    request: AssistenteRequest,
    estatisticas: StatsRead,
) -> list[dict[str, str]]:
    """Monta o array de mensagens para a API de chat."""
    sistema = (
        f"{_INSTRUCAO_SISTEMA}\n\n"
        "=== CONHECIMENTO DO PROJETO ===\n"
        f"{_carregar_guia()}\n\n"
        "=== RELATÓRIO DE ESTATÍSTICAS DO BANCO (use para responder "
        "perguntas sobre números atuais) ===\n"
        f"{_descrever_estatisticas(estatisticas)}"
    )

    mensagens = [{"role": "system", "content": sistema}]
    mensagens.extend(
        {"role": item.role, "content": item.content}
        for item in request.historico[-HISTORICO_MAX_MENSAGENS:]
    )
    mensagens.append({"role": "user", "content": request.mensagem})
    return mensagens


def _verificar_configuracao() -> None:
    if not settings.ASSISTENTE_HABILITADO:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="O assistente está desativado neste ambiente.",
        )
    if not settings.OPENROUTER_API_KEY:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=(
                "O assistente ainda não foi configurado: defina "
                "OPENROUTER_API_KEY no .env do backend."
            ),
        )


def _verificar_limite(user_id: int) -> None:
    """Aplica o intervalo mínimo entre perguntas e a cota diária."""
    hoje = date.today().isoformat()
    registro = _envios_do_dia.get(user_id)
    usados = registro[1] if registro and registro[0] == hoje else 0

    if usados >= LIMITE_DIARIO:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=(
                "Você atingiu o limite diário de perguntas ao assistente. "
                "Tente novamente amanhã."
            ),
        )

    agora = time.monotonic()
    ultimo = _ultimo_envio.get(user_id)
    if ultimo is not None and agora - ultimo < INTERVALO_MINIMO_SEGUNDOS:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=(
                "Aguarde alguns segundos antes de enviar a próxima "
                "pergunta."
            ),
        )

    _ultimo_envio[user_id] = agora
    _envios_do_dia[user_id] = (hoje, usados + 1)


def reiniciar_limites() -> None:
    """Limpa o controle de uso em memória (útil em testes)."""
    _ultimo_envio.clear()
    _envios_do_dia.clear()


def _cabecalhos() -> dict[str, str]:
    cabecalhos = {
        "Authorization": f"Bearer {settings.OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
    }
    if settings.OPENROUTER_SITE_URL:
        cabecalhos["HTTP-Referer"] = settings.OPENROUTER_SITE_URL
    if settings.OPENROUTER_SITE_NAME:
        cabecalhos["X-Title"] = settings.OPENROUTER_SITE_NAME
    return cabecalhos


def _erro_indisponivel(mensagem: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail=mensagem,
    )


def _erro_provedor(mensagem: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_502_BAD_GATEWAY,
        detail=mensagem,
    )


def _extrair_conteudo(payload: dict) -> str:
    escolhas = payload.get("choices") or []
    if not escolhas:
        return ""
    mensagem = escolhas[0].get("message") or {}
    return (mensagem.get("content") or "").strip()


def _chamar_openrouter(mensagens: list[dict[str, str]]) -> str:
    """Executa a chamada e converte falhas em HTTPException amigáveis."""
    try:
        resposta = requests.post(
            OPENROUTER_URL,
            headers=_cabecalhos(),
            json={
                "model": settings.OPENROUTER_MODEL,
                "messages": mensagens,
                "temperature": TEMPERATURA_ASSISTENTE,
            },
            timeout=settings.OPENROUTER_TIMEOUT,
        )
    except requests.exceptions.Timeout as exc:
        raise _erro_indisponivel(
            "O assistente demorou demais para responder. Tente novamente."
        ) from exc
    except requests.exceptions.RequestException as exc:
        raise _erro_indisponivel(
            "O assistente está indisponível agora. Tente novamente em "
            "alguns minutos."
        ) from exc

    if resposta.status_code in {401, 403}:
        raise _erro_indisponivel(
            "A chave do OpenRouter não está válida. Atualize "
            "OPENROUTER_API_KEY no .env do backend."
        )
    if resposta.status_code == 429:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=(
                "O limite de uso gratuito do OpenRouter foi atingido. "
                "Tente novamente mais tarde."
            ),
        )
    if resposta.status_code == 402:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=(
                "O limite de crédito do OpenRouter foi atingido. Modelos "
                "gratuitos voltam a funcionar quando a cota diária for "
                "renovada."
            ),
        )
    if resposta.status_code != 200:
        raise _erro_provedor(
            "O provedor de IA retornou um erro inesperado. Tente novamente."
        )

    try:
        payload = resposta.json()
    except ValueError as exc:
        raise _erro_provedor(
            "O provedor de IA respondeu em um formato inesperado. Tente "
            "novamente."
        ) from exc

    if isinstance(payload, dict) and payload.get("error"):
        raise _erro_provedor(
            "O provedor de IA não conseguiu responder agora. Tente "
            "novamente."
        )

    conteudo = _extrair_conteudo(payload) if isinstance(payload, dict) else ""
    if not conteudo:
        raise _erro_provedor(
            "O assistente respondeu em branco. Reformule a pergunta e tente "
            "de novo."
        )
    return conteudo


def obter_resposta(
    session: Session,
    request: AssistenteRequest,
    user_id: int,
) -> tuple[str, str]:
    """Gera a resposta do assistente para uma pergunta autenticada."""
    _verificar_configuracao()
    _verificar_limite(user_id)

    estatisticas = stats_service.get_stats(session)
    mensagens = _montar_mensagens(request, estatisticas)
    resposta = _chamar_openrouter(mensagens)
    return resposta, settings.OPENROUTER_MODEL
