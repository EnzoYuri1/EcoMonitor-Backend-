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

    # Assistente de IA (OpenRouter)
    ASSISTENTE_HABILITADO: bool = (
        os.getenv("ASSISTENTE_HABILITADO", "true").strip().lower()
        in {"1", "true", "sim", "yes"}
    )
    OPENROUTER_API_KEY: str = os.getenv("OPENROUTER_API_KEY", "")
    OPENROUTER_MODEL: str = os.getenv("OPENROUTER_MODEL", "openrouter/free")
    OPENROUTER_TIMEOUT: int = int(os.getenv("OPENROUTER_TIMEOUT", "30"))
    OPENROUTER_SITE_URL: str = os.getenv("OPENROUTER_SITE_URL", "")
    OPENROUTER_SITE_NAME: str = os.getenv("OPENROUTER_SITE_NAME", "")

    # Configurações da Central de Informações Ambientais
    CENTRAL_CONTACT_EMAIL: str = os.getenv(
        "CENTRAL_CONTACT_EMAIL", "contato@ecomonitor.local"
    )
    OPENALEX_API_KEY: str = os.getenv("OPENALEX_API_KEY", "")
    GNEWS_API_KEY: str = os.getenv("GNEWS_API_KEY", "")
    FIRMS_MAP_KEY: str = os.getenv("FIRMS_MAP_KEY", "")
    CENTRAL_HTTP_TIMEOUT: int = int(os.getenv("CENTRAL_HTTP_TIMEOUT", "15"))
    CENTRAL_RATE_LIMIT_PER_MIN: int = int(
        os.getenv("CENTRAL_RATE_LIMIT_PER_MIN", "60")
    )
    CENTRAL_NEWS_REFRESH_HOURS: int = int(
        os.getenv("CENTRAL_NEWS_REFRESH_HOURS", "3")
    )
    CENTRAL_ARTICLES_REFRESH_HOURS: int = int(
        os.getenv("CENTRAL_ARTICLES_REFRESH_HOURS", "24")
    )
    CENTRAL_MONITORING_REFRESH_HOURS: int = int(
        os.getenv("CENTRAL_MONITORING_REFRESH_HOURS", "24")
    )
    CENTRAL_SCHEDULER_ENABLED: bool = (
        os.getenv("CENTRAL_SCHEDULER_ENABLED", "false").lower() == "true"
    )


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

if settings.OPENROUTER_TIMEOUT <= 0:
    raise RuntimeError(
        "OPENROUTER_TIMEOUT deve ser um número de segundos positivo."
    )
