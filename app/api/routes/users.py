from fastapi import APIRouter

router = APIRouter(prefix="/users", tags=["users"])


@router.get("/me")
def get_service_user_profile() -> dict[str, str]:
    """获取当前服务用户信息。

    说明：此处先返回占位结构，后续接入认证与数据库。
    """
    return {"message": "TODO: 获取服务用户信息"}
