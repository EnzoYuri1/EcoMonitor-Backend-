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
