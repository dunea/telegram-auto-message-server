"""消息发送与发送记录 API 路由。

提供消息发送、发送记录查询与来源标记透传能力。
"""

from fastapi import APIRouter, Depends, Query

from app.api.deps import get_current_user, get_telegram_service
from app.api.http_errors import map_http_exceptions
from app.schema.message import SendMessageRequest, SendMessageResult
from app.service.telegram_service import TelegramService

router = APIRouter(prefix="/messages", tags=["messages"], dependencies=[Depends(get_current_user)])


@router.get("/records")
async def list_send_records(
    account_id: int = Query(..., ge=1),
    limit: int = Query(default=50, ge=1, le=200),
    telegram_service: TelegramService = Depends(get_telegram_service),
) -> list[dict]:
    """按账户查询最近发送记录。

    - account_id: 必填参数，账户标识。
    - limit: 分页窗口大小，限制在 [1, 200]。

    审查关注点：
    - 该接口用于发送行为追溯，建议与 account_id 维度审计日志联动排查；
    - limit 上限用于控制查询成本，避免批量导出式访问。
    """
    return telegram_service.ListSendRecords(account_id=account_id, limit=limit)


@router.post("/send", response_model=SendMessageResult)
async def send_message(
    payload: SendMessageRequest,
    telegram_service: TelegramService = Depends(get_telegram_service),
) -> SendMessageResult:
    """发送一条消息并返回标准化结果。

    本接口支持纯文本与多媒体消息：
    - target_identifier: 目标标识，支持用户名、用户 ID 或群组标识；
    - 当 payload.message_content 为空时，默认按 text 类型发送；
    - 当 message_content 存在时，将其展开为服务层所需的扁平字段；
    - media_items 会被转换为字典列表并按 sort_order 交由服务层处理。

    source_type 标识消息来源，支持以下取值：
    - manual: 手动发送
    - scheduled: 定时任务发送
    - rule: 规则触发发送
    - auto_reply: 自动回复发送

    审查关注点：
    - payload.content 与 message_content.text_content 均存在长度上限（schema 约束）；
    - media_items 会被序列化后透传至服务层，排序字段 sort_order 影响最终发送顺序；
    - source_type 会进入发送记录，属于审计与追溯的关键字段。

    业务校验失败时，ValueError 映射为 404。
    """
    with map_http_exceptions((ValueError, 404)):
        message_content = payload.message_content
        result = await telegram_service.SendMessage(
            account_id=payload.account_id,
            target_identifier=payload.target_identifier,
            content=payload.content,
            content_type=(message_content.content_type if message_content else "text"),
            text_content=(message_content.text_content if message_content else None),
            media_type=(message_content.media_type if message_content else None),
            media_url=(message_content.media_url if message_content else None),
            media_key=(message_content.media_key if message_content else None),
            emoji=(message_content.emoji if message_content else None),
            caption=(message_content.caption if message_content else None),
            media_items=([
                # 将 Pydantic 子项转换为服务层可直接消费的序列化结构。
                {
                    "media_type": item.media_type,
                    "media_url": item.media_url,
                    "media_key": item.media_key,
                    "caption": item.caption,
                    "sort_order": item.sort_order,
                }
                for item in message_content.media_items
            ] if message_content else None),
            source_type=payload.source_type,
        )
        return SendMessageResult(**result)
