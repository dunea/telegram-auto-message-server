from fastapi import APIRouter

from app.api.routes import health, accounts, tasks, messages, users, service_status


def build_api_router() -> APIRouter:
    router = APIRouter(prefix="/api/v1")
    router.include_router(health.router)
    router.include_router(users.router)
    router.include_router(accounts.router)
    router.include_router(tasks.router)
    router.include_router(messages.router)
    router.include_router(service_status.router)
    return router
