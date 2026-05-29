from typing import Any

from sqlalchemy.orm import Session

from app.models.task import AutoReplyRule
from app.repository.task_repository import SqlAlchemyAutoReplyRuleRepository


class AutoReplyService:
    """自动回复规则服务。"""

    def __init__(self, session: Session, auto_reply_rule_repository: SqlAlchemyAutoReplyRuleRepository) -> None:
        self._session = session
        self._auto_reply_rule_repository = auto_reply_rule_repository

    @staticmethod
    def _to_rule_dict(rule: AutoReplyRule) -> dict[str, Any]:
        return {
            "rule_id": int(rule.id),
            "account_id": int(rule.account_id),
            "trigger_keyword": rule.trigger_keyword,
            "reply_content": rule.reply_content,
            "is_active": bool(rule.is_active),
        }

    def CreateRule(self, account_id: int, trigger_keyword: str, reply_content: str) -> dict[str, Any]:
        rule = AutoReplyRule(
            account_id=account_id,
            trigger_keyword=trigger_keyword.strip(),
            reply_content=reply_content.strip(),
            is_active=True,
        )
        self._auto_reply_rule_repository.Save(rule)
        self._session.commit()
        return self._to_rule_dict(rule)

    def GetRuleById(self, rule_id: int) -> dict[str, Any]:
        rule = self._auto_reply_rule_repository.FindById(rule_id)
        if rule is None:
            raise ValueError("回复消息不存在")
        return self._to_rule_dict(rule)

    def UpdateRule(self, rule_id: int, trigger_keyword: str, reply_content: str) -> dict[str, Any]:
        rule = self._auto_reply_rule_repository.UpdateById(
            rule_id=rule_id,
            trigger_keyword=trigger_keyword.strip(),
            reply_content=reply_content.strip(),
        )
        if rule is None:
            raise ValueError("回复消息不存在")
        self._session.commit()
        return self._to_rule_dict(rule)

    def SetRuleActive(self, rule_id: int, is_active: bool) -> dict[str, Any]:
        updated = self._auto_reply_rule_repository.UpdateIsActiveById(rule_id=rule_id, is_active=is_active)
        if not updated:
            raise ValueError("回复消息不存在")
        self._session.commit()
        return self.GetRuleById(rule_id)

    def SoftDeleteRule(self, rule_id: int) -> dict[str, Any]:
        rule = self.SetRuleActive(rule_id=rule_id, is_active=False)
        return {**rule, "deleted": True}

    def ListRulesByAccountId(self, account_id: int, limit: int, offset: int) -> dict[str, Any]:
        items = self._auto_reply_rule_repository.FindAllByAccountIdOrderByIdDesc(
            account_id=account_id,
            limit=limit,
            offset=offset,
        )
        total = self._auto_reply_rule_repository.CountByAccountId(account_id=account_id)
        return {
            "total": int(total),
            "items": [self._to_rule_dict(item) for item in items],
        }

    def MatchAutoReply(self, account_id: int, content: str) -> str | None:
        """按账号查找第一个命中的启用规则。"""
        normalized_content = content.strip().lower()
        if not normalized_content:
            return None
        rules = self._auto_reply_rule_repository.FindAllByAccountIdAndIsActive(account_id=account_id, is_active=True)
        for rule in rules:
            keyword = str(rule.trigger_keyword or "").strip().lower()
            if keyword and keyword in normalized_content:
                return str(rule.reply_content)
        return None
