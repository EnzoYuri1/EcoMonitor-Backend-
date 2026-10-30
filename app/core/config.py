import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parents[2]
load_dotenv(BASE_DIR / ".env")


class Settings:
    """Configurações da aplicação carregadas de variáveis de ambiente."""

    PROJECT_NAME: str = "EcoMonitor API"
    VERSION: str = "0.1.0"
    API_V1_STR: str = "/api/v1"

    SECRET_KEY: str = os.getenv("SECRET_KEY", "")
    ALGORITHM: str = os.getenv("ALGORITHM", "HS256")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = int(
        os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "60")
    )
    DATABASE_URL: str = os.getenv(
        "DATABASE_URL", "sqlite:///./data/ecomonitor.db"
    )
    CORS_ORIGINS: list[str] = [
        origin.strip()
        for origin in os.getenv("CORS_ORIGINS", "").split(",")
        if origin.strip()
    ]


settings = Settings()

if not settings.SECRET_KEY:
    raise RuntimeError(
        "SECRET_KEY não configurada. Copie .env.example para .env e "
        "gere uma chave segura."
    )
