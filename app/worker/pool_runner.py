import asyncio
from datetime import datetime

from app.config import Settings


class PoolRunner:
    """号池运行器。

    当前版本先提供最小主循环，后续在此接入：
    1. 多账号登录与在线状态检查。
    2. 会话列表、消息列表拉取。
    3. 发送任务执行与会话状态同步。
    """

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    async def run_forever(self) -> None:
        while True:
            print(f"[{datetime.utcnow().isoformat()}] pool loop tick")
            await asyncio.sleep(5)
