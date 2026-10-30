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

if settings.SECRET_KEY == "troque-por-uma-chave-secreta-gerada-localmente":
    raise RuntimeError(
        "SECRET_KEY ainda contém o valor de exemplo. Gere uma chave "
        "exclusiva com secrets.token_urlsafe(48)."
    )

if len(settings.SECRET_KEY) < 32:
    raise RuntimeError("SECRET_KEY deve ter pelo menos 32 caracteres.")

if settings.ACCESS_TOKEN_EXPIRE_MINUTES <= 0:
    raise RuntimeError("ACCESS_TOKEN_EXPIRE_MINUTES deve ser positivo.")

if "*" in settings.CORS_ORIGINS:
    raise RuntimeError(
        "CORS_ORIGINS não pode conter '*' com credenciais habilitadas."
    )
