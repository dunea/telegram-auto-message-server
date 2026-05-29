"""账户管理 API 路由。

提供 Telegram 账户的创建、上线、会话查询与历史消息查询能力。
"""

from fastapi import APIRouter, Depends, HTTPException, Query

from app.api.deps import get_telegram_service
from app.schema.account import AccountOnlineRequest, CreateAccountRequest
from app.service.telegram_service import TelegramService

router = APIRouter(prefix="/accounts", tags=["accounts"])


@router.post("")
async def create_telegram_account(
    payload: CreateAccountRequest,
    telegram_service: TelegramService = Depends(get_telegram_service),
) -> dict:
    """创建并托管一个 Telegram 账户。

    - phone_number: 目标账号手机号。
    - proxy_id: 可选代理配置 ID；为空时按默认网络策略处理。
    - session_string: 可选会话串，存在时可用于减少首次登录流程。

    审查关注点：
    - phone_number 长度边界由 schema 限制在 [3, 64]；
    - session_string 属于敏感凭据，应避免在日志中明文输出；
    - 本接口返回 400 表示请求参数或业务状态不满足创建条件。

    业务校验失败时，ValueError 映射为 400。
    """
    try:
        return telegram_service.CreateAccount(
            phone_number=payload.phone_number,
            proxy_id=payload.proxy_id,
            session_string=payload.session_string,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("")
async def list_telegram_accounts(
    telegram_service: TelegramService = Depends(get_telegram_service),
) -> list[dict]:
    """列出当前服务已托管的 Telegram 账户。"""
    return telegram_service.ListManagedAccounts()


@router.post("/{account_id}/online")
async def ensure_telegram_account_online(
    account_id: int,
    payload: AccountOnlineRequest,
    telegram_service: TelegramService = Depends(get_telegram_service),
) -> dict:
    """确保指定账户处于在线可发送状态。

    若请求体携带 session_string，会先更新本地会话串，再触发上线流程。

    审查关注点：
    - 仅在显式传入 session_string 时更新，避免误覆盖已有会话；
    - 404 表示账户不存在或当前状态不允许上线。

    业务校验失败时，ValueError 映射为 404。
    """
    try:
        if payload.session_string:
            # 仅在调用方显式提供新会话串时更新，避免覆盖已存档会话。
            telegram_service.UpdateAccountSessionString(account_id=account_id, session_string=payload.session_string)
        return await telegram_service.EnsureAccountOnline(account_id=account_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/{account_id}/conversations")
async def list_telegram_conversations(
    account_id: int,
    limit: int = Query(default=50, ge=1, le=200),
    telegram_service: TelegramService = Depends(get_telegram_service),
) -> list[dict]:
    """查询账户最近会话列表。

    limit 通过 Query 约束在 [1, 200]，避免一次性拉取过多记录造成接口压力。

    审查关注点：
    - 会话读取为在线能力依赖链的一部分，404 常见于账户不可用；
    - limit 上限用于限制单次查询成本，避免放大 I/O 峰值。
    """
    try:
        return await telegram_service.ListConversations(account_id=account_id, limit=limit)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/{account_id}/messages/{target_identifier}")
async def list_telegram_messages(
    account_id: int,
    target_identifier: str,
    limit: int = Query(default=50, ge=1, le=200),
    telegram_service: TelegramService = Depends(get_telegram_service),
) -> list[dict]:
    """查询账户与指定目标的消息记录。

    - target_identifier: 目标标识，支持用户名、用户 ID 或群组标识（由服务层解析）。

    审查关注点：
    - target_identifier 的实际解析规则在服务层，路由层仅负责透传；
    - limit 上限用于控制历史消息读取窗口，防止单请求过重。

    业务校验失败时，ValueError 映射为 404。
    """
    try:
        return await telegram_service.ListMessages(
            account_id=account_id,
            target_identifier=target_identifier,
            limit=limit,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
