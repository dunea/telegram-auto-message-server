class MessageService:
    """消息业务服务。"""

    def SendMessage(self, account_id: int, target_identifier: str, content: str) -> dict:
        """发送消息占位实现。"""
        return {
            "account_id": account_id,
            "target_identifier": target_identifier,
            "content": content,
            "status": "queued",
        }
