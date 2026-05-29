"""用户信息 API 路由（占位）。

当前用于保留用户域路由入口，后续接入鉴权与用户仓储后再返回真实数据。
"""

from fastapi import APIRouter

router = APIRouter(prefix="/users", tags=["users"])


@router.get("/me")
def get_service_user_profile() -> dict[str, str]:
    """获取当前服务用户信息。

    关键点：
    - 当前仅返回占位结构；
    - 后续在此处衔接认证上下文与用户数据源。
    """
    return {"message": "TODO: 获取服务用户信息"}
