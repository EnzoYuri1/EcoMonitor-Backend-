from typing import Generic, TypeVar

from pydantic import BaseModel, ConfigDict, Field

T = TypeVar("T")


class Page(BaseModel, Generic[T]):
    """Estrutura padrão para respostas paginadas."""

    items: list[T] = Field(description="Itens da página atual.")
    total: int = Field(ge=0, description="Total de itens encontrados.")
    page: int = Field(ge=1, description="Página atual.")
    page_size: int = Field(ge=1, description="Quantidade de itens por página.")
    pages: int = Field(ge=0, description="Total de páginas.")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "items": [],
                "total": 0,
                "page": 1,
                "page_size": 20,
                "pages": 0,
            }
        }
    )
