from fastapi import APIRouter

from app.api.v1.endpoints import assistente, auth, central, ocorrencias, stats

api_router = APIRouter()
api_router.include_router(auth.router)
api_router.include_router(ocorrencias.router)
api_router.include_router(stats.router)
api_router.include_router(assistente.router)
api_router.include_router(central.router)
