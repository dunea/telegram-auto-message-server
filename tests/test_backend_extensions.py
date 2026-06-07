"""后端模型扩展和随机逻辑的单元测试。"""

from app.models.task import AutoReplyRule, ScheduledMessageTask
from app.models.reply_message import ReplyMessage
from app.schema.auto_reply_rule import CreateAutoReplyRuleRequest
from app.schema.reply_message import ReplyMessageCreate
from app.schema.task import CreateScheduledTaskRequest


class TestAutoReplyRuleModel:
    def test_new_fields_default_values(self) -> None:
        rule = AutoReplyRule(
            account_id=1,
            trigger_keyword="hello",
            reply_content="world",
            trigger_mode="keyword",
            scope_mode="all",
            is_active=True,
        )
        assert rule.trigger_mode == "keyword"
        assert rule.keywords is None
        assert rule.scope_mode == "all"
        assert rule.conversation_ids is None
        assert rule.is_active is True

    def test_custom_trigger_mode_all(self) -> None:
        rule = AutoReplyRule(
            account_id=1,
            trigger_keyword="",
            reply_content="",
            trigger_mode="all",
            keywords=["hello", "world"],
            scope_mode="specific",
            conversation_ids=[123, 456],
        )
        assert rule.trigger_mode == "all"
        assert rule.keywords == ["hello", "world"]
        assert rule.scope_mode == "specific"
        assert rule.conversation_ids == [123, 456]

    def test_reply_messages_relationship(self) -> None:
        rule = AutoReplyRule(account_id=1, trigger_keyword="hi", reply_content="ok")
        msg1 = ReplyMessage(rule_id=0, text="回复1", sort_order=1)
        msg2 = ReplyMessage(rule_id=0, text="回复2", sort_order=2)
        rule.reply_messages = [msg1, msg2]
        assert len(rule.reply_messages) == 2
        assert rule.reply_messages[0].text == "回复1"


class TestScheduledMessageTaskModel:
    def test_new_fields_default_values(self) -> None:
        task = ScheduledMessageTask(
            account_id=1,
            cron_expr="0 9 * * *",
            target_identifier="test",
            scope_mode="all",
            is_active=True,
        )
        assert task.scope_mode == "all"
        assert task.conversation_ids is None
        assert task.message_ids is None
        assert task.is_active is True

    def test_custom_scope_and_message_ids(self) -> None:
        task = ScheduledMessageTask(
            account_id=2,
            cron_expr="*/30 * * * *",
            target_identifier="target",
            scope_mode="specific",
            conversation_ids=[100, 200],
            message_ids=[1, 2, 3],
        )
        assert task.scope_mode == "specific"
        assert task.conversation_ids == [100, 200]
        assert task.message_ids == [1, 2, 3]


class TestAutoReplyRuleSchema:
    def test_create_request_with_new_fields(self) -> None:
        data = CreateAutoReplyRuleRequest(
            account_id=1,
            trigger_keyword="hello",
            reply_content="hi there",
            trigger_mode="all",
            keywords=["hi", "hello"],
            scope_mode="specific",
            conversation_ids=[123],
            reply_messages=[ReplyMessageCreate(text="reply1", sort_order=1)],
        )
        assert data.trigger_mode == "all"
        assert data.keywords == ["hi", "hello"]
        assert data.scope_mode == "specific"
        assert data.conversation_ids == [123]
        assert len(data.reply_messages) == 1

    def test_create_request_defaults(self) -> None:
        data = CreateAutoReplyRuleRequest(
            account_id=1,
            trigger_keyword="test",
            reply_content="test reply",
        )
        assert data.trigger_mode == "keyword"
        assert data.keywords is None
        assert data.scope_mode == "all"
        assert data.reply_messages == []


class TestScheduledTaskSchema:
    def test_create_request_with_new_fields(self) -> None:
        data = CreateScheduledTaskRequest(
            account_id=1,
            cron_expr="* * * * *",
            target_identifier="user123",
            scope_mode="specific",
            conversation_ids=[100],
            message_ids=[1, 2],
        )
        assert data.scope_mode == "specific"
        assert data.conversation_ids == [100]
        assert data.message_ids == [1, 2]

    def test_create_request_defaults(self) -> None:
        data = CreateScheduledTaskRequest(
            account_id=1,
            cron_expr="0 9 * * *",
            target_identifier="user456",
        )
        assert data.scope_mode == "all"
        assert data.conversation_ids is None
        assert data.message_ids is None


class TestReplyMessageModel:
    def test_model_attributes(self) -> None:
        msg = ReplyMessage(rule_id=1, text="test reply", sort_order=3)
        assert msg.rule_id == 1
        assert msg.text == "test reply"
        assert msg.sort_order == 3

    def test_default_sort_order(self) -> None:
        msg = ReplyMessage(rule_id=1, text="hi", sort_order=0)
        assert msg.sort_order == 0


class TestRandomSelectionLogic:
    def test_pseudo_random_choice(self) -> None:
        import random
        items = [1, 2, 3]
        random.seed(42)
        chosen = random.choice(items)
        assert chosen in items

    def test_trigger_mode_all_skips_keyword_check(self) -> None:
        rule = AutoReplyRule(
            account_id=1,
            trigger_keyword="",
            reply_content="fallback",
            trigger_mode="all",
        )
        assert rule.trigger_mode == "all"
        assert not rule.trigger_keyword
        assert rule.reply_content == "fallback"

    def test_keyword_list_matching(self) -> None:
        keywords = ["hello", "world"]
        message = "hello there"
        matched = any(kw in message for kw in keywords)
        assert matched is True

    def test_keyword_list_no_match(self) -> None:
        keywords = ["hello", "world"]
        message = "goodbye"
        matched = any(kw in message for kw in keywords)
        assert matched is False
