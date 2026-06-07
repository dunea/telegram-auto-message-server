import random
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
            "trigger_mode": rule.trigger_mode,
            "keywords": rule.keywords,
            "scope_mode": rule.scope_mode,
            "conversation_ids": rule.conversation_ids,
        }

    def CreateRule(
        self,
        account_id: int,
        trigger_keyword: str = "",
        reply_content: str = "",
        trigger_mode: str = "keyword",
        keywords: list[str] | None = None,
        scope_mode: str = "all",
        conversation_ids: list[int] | None = None,
    ) -> dict[str, Any]:
        rule = AutoReplyRule(
            account_id=account_id,
            trigger_keyword=trigger_keyword.strip(),
            reply_content=reply_content.strip(),
            is_active=True,
            trigger_mode=trigger_mode,
            keywords=keywords,
            scope_mode=scope_mode,
            conversation_ids=conversation_ids,
        )
        self._auto_reply_rule_repository.Save(rule)
        self._session.commit()
        return self._to_rule_dict(rule)

    def GetRuleById(self, rule_id: int) -> dict[str, Any]:
        rule = self._auto_reply_rule_repository.FindById(rule_id)
        if rule is None:
            raise ValueError("回复消息不存在")
        return self._to_rule_dict(rule)

    def UpdateRule(
        self,
        rule_id: int,
        trigger_keyword: str | None = None,
        reply_content: str | None = None,
        trigger_mode: str | None = None,
        keywords: list[str] | None = None,
        scope_mode: str | None = None,
        conversation_ids: list[int] | None = None,
    ) -> dict[str, Any]:
        kwargs = {}
        if trigger_keyword is not None:
            kwargs["trigger_keyword"] = trigger_keyword.strip()
        if reply_content is not None:
            kwargs["reply_content"] = reply_content.strip()
        if trigger_mode is not None:
            kwargs["trigger_mode"] = trigger_mode
        if keywords is not None:
            kwargs["keywords"] = keywords
        if scope_mode is not None:
            kwargs["scope_mode"] = scope_mode
        if conversation_ids is not None:
            kwargs["conversation_ids"] = conversation_ids
        rule = self._auto_reply_rule_repository.UpdateById(rule_id=rule_id, **kwargs)
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

    def MatchAutoReply(self, account_id: int, content: str, peer_id: int | None = None) -> str | None:
        """按账号查找第一个命中的启用规则，支持 trigger_mode 和 scope_mode。"""
        normalized_content = content.strip().lower()
        if not normalized_content:
            return None
        rules = self._auto_reply_rule_repository.FindAllByAccountIdAndIsActive(
            account_id=account_id, is_active=True
        )
        for rule in rules:
            if rule.trigger_mode == "keyword":
                keywords = rule.keywords
                if not keywords:
                    keyword = str(rule.trigger_keyword or "").strip().lower()
                    if not keyword or keyword not in normalized_content:
                        continue
                else:
                    matched = any(
                        str(kw or "").strip().lower() in normalized_content
                        for kw in keywords
                    )
                    if not matched:
                        continue

            if rule.scope_mode == "specific" and peer_id is not None:
                conv_ids = rule.conversation_ids
                if conv_ids and peer_id not in conv_ids:
                    continue

            reply_messages = rule.reply_messages
            if reply_messages:
                chosen = random.choice(reply_messages)
                return chosen.text
            if rule.reply_content:
                return str(rule.reply_content)
            return None
        return None
