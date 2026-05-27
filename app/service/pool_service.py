class PoolService:
    """号池调度服务。"""

    def SelectNextAccountForDispatch(self) -> int | None:
        """按策略选择下一个可执行账号。"""
        return None
