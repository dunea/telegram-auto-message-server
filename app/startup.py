import asyncio
from typing import NoReturn

from fastapi import FastAPI

from app.api.router import build_api_router
from app.config import Settings
from app.worker.pool_runner import PoolRunner


def create_api_application(settings: Settings) -> FastAPI:
    """创建 API 模式应用。"""
    app = FastAPI(title=settings.app_name)
    app.include_router(build_api_router())
    return app


async def run_pool_mode(settings: Settings) -> NoReturn:
    """启动号池模式。

    号池模式不暴露业务 HTTP 接口，专注执行账号巡检、会话同步与消息发送。
    """
    runner = PoolRunner(settings=settings)
    await runner.run_forever()


def run_pool_mode_blocking(settings: Settings) -> NoReturn:
    asyncio.run(run_pool_mode(settings))
