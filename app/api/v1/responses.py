from typing import Any

UNAUTHORIZED_RESPONSE: dict[str, Any] = {
    "description": "Token ausente, inválido ou expirado."
}

FORBIDDEN_RESPONSE: dict[str, Any] = {
    "description": "Usuário não é o responsável pela ocorrência."
}

NOT_FOUND_RESPONSE: dict[str, Any] = {
    "description": "Ocorrência não encontrada."
}

BAD_REQUEST_RESPONSE: dict[str, Any] = {
    "description": (
        "Período inválido: a data inicial não pode ser posterior à data "
        "final."
    )
}

CONFLICT_RESPONSE: dict[str, Any] = {
    "description": "Email já cadastrado."
}

VALIDATION_ERROR_RESPONSE: dict[str, Any] = {
    "description": (
        "Dados inválidos. Verifique os campos obrigatórios, os formatos "
        "e os limites de cada campo."
    ),
    "content": {
        "application/json": {
            "example": {
                "detail": [
                    {
                        "type": "string_too_short",
                        "loc": ["body", "senha"],
                        "msg": "String should have at least 8 characters",
                        "input": "123",
                    }
                ]
            }
        }
    },
}

RATE_LIMIT_RESPONSE: dict[str, Any] = {
    "description": (
        "Limite de uso do assistente atingido: intervalo mínimo entre "
        "perguntas, cota diária por usuário ou cota gratuita do OpenRouter."
    )
}

UPSTREAM_ERROR_RESPONSE: dict[str, Any] = {
    "description": (
        "O provedor de IA retornou um erro inesperado, resposta vazia ou "
        "formato inválido."
    )
}

UNAVAILABLE_RESPONSE: dict[str, Any] = {
    "description": (
        "Assistente indisponível: desativado neste ambiente, sem "
        "OPENROUTER_API_KEY configurada, chave inválida, tempo de espera "
        "excedido ou falha de conexão com o OpenRouter."
    )
}
