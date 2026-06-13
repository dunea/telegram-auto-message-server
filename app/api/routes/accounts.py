"""账户管理 API 路由。

提供 Telegram 账户的创建、上线、会话查询与历史消息查询能力。
"""

from fastapi import APIRouter, Depends, Query

from app.api.deps import get_telegram_service, get_current_user
from app.api.http_errors import map_http_exceptions
from app.schema.account import (
    AccountOnlineRequest,
    AccountStatusResponse,
    CreateAccountRequest,
    CreateAccountWithSessionRequest,
    LoginStepResponse,
    RequestPhoneLoginCodeRequest,
    UpdateAccountActiveRequest,
    VerifyPhoneCodeRequest,
    VerifyTwoFactorPasswordRequest,
)
from app.service.telegram_service import TelegramService

router = APIRouter(prefix="/accounts", tags=["accounts"], dependencies=[Depends(get_current_user)])


@router.post("")
async def create_telegram_account(
    payload: CreateAccountRequest,
    telegram_service: TelegramService = Depends(get_telegram_service),
    current_user = Depends(get_current_user),
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
    with map_http_exceptions((ValueError, 400)):
        return await telegram_service.CreateAccount(
            phone_number=payload.phone_number,
            proxy_id=payload.proxy_id,
            session_string=payload.session_string,
            owner_user_id=current_user.id,
        )


@router.post("/login/phone/request-code", response_model=LoginStepResponse)
async def request_phone_login_code(
    payload: RequestPhoneLoginCodeRequest,
    telegram_service: TelegramService = Depends(get_telegram_service),
    current_user = Depends(get_current_user),
) -> LoginStepResponse:
    """通过手机号请求验证码。"""
    with map_http_exceptions((ValueError, 400)):
        result = await telegram_service.RequestPhoneLoginCode(
            phone_number=payload.phone_number,
            proxy_id=payload.proxy_id,
            owner_user_id=current_user.id,
        )
        return LoginStepResponse(**result)


@router.post("/{account_id}/login/phone/verify-code", response_model=LoginStepResponse)
async def verify_phone_login_code(
    account_id: int,
    payload: VerifyPhoneCodeRequest,
    telegram_service: TelegramService = Depends(get_telegram_service),
    current_user = Depends(get_current_user),
) -> LoginStepResponse:
    """提交验证码并推进登录状态。"""
    with map_http_exceptions((ValueError, 404)):
        result = await telegram_service.VerifyPhoneLoginCode(
            account_id=account_id,
            phone_code_hash=payload.phone_code_hash,
            code=payload.code,
            owner_user_id=current_user.id,
        )
        return LoginStepResponse(**result)


@router.post("/{account_id}/login/phone/verify-password", response_model=LoginStepResponse)
async def verify_two_factor_password(
    account_id: int,
    payload: VerifyTwoFactorPasswordRequest,
    telegram_service: TelegramService = Depends(get_telegram_service),
    current_user = Depends(get_current_user),
) -> LoginStepResponse:
    """提交二级密码完成登录。"""
    with map_http_exceptions((ValueError, 404)):
        result = await telegram_service.VerifyTwoFactorPassword(
            account_id=account_id,
            password=payload.password,
            owner_user_id=current_user.id,
        )
        return LoginStepResponse(**result)


@router.post("/login/session", response_model=LoginStepResponse)
async def create_account_with_session_login(
    payload: CreateAccountWithSessionRequest,
    telegram_service: TelegramService = Depends(get_telegram_service),
    current_user = Depends(get_current_user),
) -> LoginStepResponse:
    """通过 session 串登录并托管账号。"""
    with map_http_exceptions((ValueError, 400)):
        result = await telegram_service.CreateAccountWithSessionLogin(
            phone_number=payload.phone_number,
            session_string=payload.session_string,
            proxy_id=payload.proxy_id,
            owner_user_id=current_user.id,
        )
        return LoginStepResponse(**result)


@router.get("")
async def list_telegram_accounts(
    telegram_service: TelegramService = Depends(get_telegram_service),
    current_user = Depends(get_current_user),
) -> list[dict]:
    """列出当前服务已托管的 Telegram 账户。"""
    return await telegram_service.ListManagedAccounts(owner_user_id=current_user.id)


@router.patch("/{account_id}/active", response_model=AccountStatusResponse)
async def update_account_active(
    account_id: int,
    payload: UpdateAccountActiveRequest,
    telegram_service: TelegramService = Depends(get_telegram_service),
    current_user = Depends(get_current_user),
) -> AccountStatusResponse:
    """启用或停用账号。"""
    with map_http_exceptions((ValueError, 404)):
        result = await telegram_service.SetAccountActive(
            account_id=account_id,
            is_active=payload.is_active,
            owner_user_id=current_user.id,
        )
        return AccountStatusResponse(**result)


@router.delete("/{account_id}")
async def soft_delete_account(
    account_id: int,
    telegram_service: TelegramService = Depends(get_telegram_service),
    current_user = Depends(get_current_user),
) -> dict:
    """软删除账号。"""
    with map_http_exceptions((ValueError, 404)):
        return await telegram_service.SoftDeleteAccount(account_id=account_id, owner_user_id=current_user.id)


@router.post("/{account_id}/online")
async def ensure_telegram_account_online(
    account_id: int,
    payload: AccountOnlineRequest,
    telegram_service: TelegramService = Depends(get_telegram_service),
    current_user = Depends(get_current_user),
) -> dict:
    """确保指定账户处于在线可发送状态。

    若请求体携带 session_string，会先更新本地会话串，再触发上线流程。

    审查关注点：
    - 仅在显式传入 session_string时更新，避免误覆盖已有会话；
    - 404 表示账户不存在或当前状态不允许上线。

    业务校验失败时，ValueError 映射为 404。
    """
    with map_http_exceptions((ValueError, 404)):
        if payload.session_string:
            await telegram_service.UpdateAccountSessionString(
                account_id=account_id,
                session_string=payload.session_string,
                owner_user_id=current_user.id,
            )
        return await telegram_service.EnsureAccountOnline(account_id=account_id, owner_user_id=current_user.id)


@router.get("/{account_id}/conversations")
async def list_telegram_conversations(
    account_id: int,
    limit: int = Query(default=50, ge=1, le=200),
    telegram_service: TelegramService = Depends(get_telegram_service),
    current_user = Depends(get_current_user),
) -> list[dict]:
    """查询账户最近会话列表。

    limit 通过 Query 约束在 [1, 200]，避免一次性拉取过多记录造成接口压力。

    审查关注点：
    - 会话读取为在线能力依赖链的一部分，404 常见于账户不可用；
    - limit 上限用于限制单次查询成本，避免放大 I/O 峰值。
    """
    with map_http_exceptions((ValueError, 404)):
        return await telegram_service.ListConversations(account_id=account_id, limit=limit, owner_user_id=current_user.id)


@router.get("/{account_id}/messages/{target_identifier}")
async def list_telegram_messages(
    account_id: int,
    target_identifier: str,
    limit: int = Query(default=50, ge=1, le=200),
    telegram_service: TelegramService = Depends(get_telegram_service),
    current_user = Depends(get_current_user),
) -> list[dict]:
    """查询账户与指定目标的消息记录。

    - target_identifier: 目标标识，支持用户名、用户 ID 或群组标识（由服务层解析）。

    审查关注点：
    - target_identifier 的实际解析规则在服务层，路由层仅负责透传；
    - limit 上限用于控制历史消息读取窗口，防止单请求过重。

    业务校验失败时，ValueError 映射为 404。
    """
    with map_http_exceptions((ValueError, 404)):
        return await telegram_service.ListMessages(
            account_id=account_id,
            target_identifier=target_identifier,
            limit=limit,
            owner_user_id=current_user.id,
        )
