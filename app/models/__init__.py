"""ORM 模型包。

导入本包时会顺带注册所有模型与枚举，避免元数据加载不完整。
"""

from app.models.account import ProxyInfo, TelegramAccount
from app.models.enums import (
	ErrorClass,
	MessageAttemptStatus,
	MessageContentType,
	MessageDirection,
	MessageMediaType,
	MessageSendStatus,
	MessageSourceType,
	TaskExecutionStatus,
	TelegramPeerType,
)
from app.models.file import FileRecord
from app.models.message import (
	MessageContent,
	MessageContentMedia,
	TelegramMessage,
	TelegramMessageMedia,
	TelegramMessageSendAttempt,
)
from app.models.task import (
	AutoReplyRule,
	RuleMessageTask,
	ScheduledMessageTask,
	TaskExecutionLog,
	UserReplySample,
)
from app.models.user import User
