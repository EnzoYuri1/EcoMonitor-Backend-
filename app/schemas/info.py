from pydantic import BaseModel, ConfigDict, Field


class InfoRead(BaseModel):
    """Links e metadados da API."""

    nome: str = Field(description="Nome da API.")
    versao: str = Field(description="Versão atual da API.")
    docs: str = Field(description="Documentação interativa (RapiDoc).")
    swagger: str = Field(description="Documentação alternativa (Swagger UI).")
    redoc: str = Field(description="Documentação alternativa (ReDoc).")
    openapi: str = Field(description="Especificação OpenAPI em JSON.")
    health: str = Field(description="Verificação de disponibilidade.")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "nome": "EcoMonitor API",
                "versao": "0.1.0",
                "docs": "/docs",
                "swagger": "/swagger",
                "redoc": "/redoc",
                "openapi": "/openapi.json",
                "health": "/health",
            }
        }
    )
