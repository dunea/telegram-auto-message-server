import importlib

from app.config import get_settings
from app.startup import create_api_application, run_pool_mode_blocking


def main() -> None:
    """应用统一入口。

    - MODE=api: 启动 FastAPI。
    - MODE=pool: 启动号池后台循环。
    """
    settings = get_settings()
    mode = settings.mode.lower().strip()

    if mode == "pool":
        run_pool_mode_blocking(settings)
        return

    api_app = create_api_application(settings)
    uvicorn_module = importlib.import_module("uvicorn")
    uvicorn_module.run(
        api_app,
        host=settings.app_host,
        port=settings.app_port,
        log_level=settings.log_level.lower(),
    )


if __name__ == "__main__":
    main()
