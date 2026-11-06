from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

MENSAGEM_MAX_CARACTERES = 1000
HISTORICO_MAX_MENSAGENS = 6


class MensagemHistorico(BaseModel):
    """Mensagem já trocada entre o usuário e o assistente."""

    role: Literal["user", "assistant"]
    content: str = Field(
        min_length=1,
        max_length=MENSAGEM_MAX_CARACTERES,
        description="Texto da mensagem da conversa.",
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "role": "user",
                "content": "O que o EcoMonitor faz?",
            }
        }
    )


class AssistenteRequest(BaseModel):
    """Corpo de uma pergunta enviada ao assistente."""

    mensagem: str = Field(
        min_length=1,
        max_length=MENSAGEM_MAX_CARACTERES,
        description=(
            "Pergunta em português com até 1.000 caracteres."
        ),
    )
    historico: list[MensagemHistorico] = Field(
        default_factory=list,
        max_length=HISTORICO_MAX_MENSAGENS,
        description=(
            "Mensagens anteriores da conversa, na ordem cronológica "
            "(no máximo as 6 últimas)."
        ),
    )

    @field_validator("mensagem")
    @classmethod
    def validar_mensagem(cls, valor: str) -> str:
        texto = valor.strip()
        if not texto:
            raise ValueError("A pergunta não pode estar vazia.")
        return texto

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "mensagem": "Como cadastro uma ocorrência de queimada?",
                "historico": [],
            }
        }
    )


class AssistenteResponse(BaseModel):
    """Resposta gerada pelo modelo configurado no OpenRouter."""

    resposta: str = Field(description="Texto da resposta em português.")
    modelo: str = Field(
        description="Modelo usado na chamada (configuração OPENROUTER_MODEL)."
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "resposta": (
                    "Para cadastrar uma queimada, clique em \"Nova "
                    "ocorrência\" no menu, selecione o tipo \"queimada\" e "
                    "preencha município, estado, descrição e data..."
                ),
                "modelo": "openrouter/free",
            }
        }
    )
