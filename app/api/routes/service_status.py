from fastapi import APIRouter

router = APIRouter(prefix="/service", tags=["service"])


@router.get("/status")
def get_service_status() -> dict[str, str]:
    return {"message": "TODO: 获取服务状态与号池状态"}
