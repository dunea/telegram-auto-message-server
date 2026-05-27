class TaskService:
    """定时任务与规则任务服务。"""

    def RegisterScheduledTask(self, payload: dict) -> dict:
        """注册定时任务。"""
        return {"result": "scheduled", "payload": payload}

    def RegisterRuleTask(self, payload: dict) -> dict:
        """注册规则任务。"""
        return {"result": "rule_registered", "payload": payload}
