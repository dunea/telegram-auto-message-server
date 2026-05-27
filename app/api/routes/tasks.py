from fastapi import APIRouter

router = APIRouter(prefix="/tasks", tags=["tasks"])


@router.post("/schedule")
def create_schedule_task() -> dict[str, str]:
    return {"message": "TODO: 设置定时发送消息"}


@router.post("/rule")
def create_rule_task() -> dict[str, str]:
    return {"message": "TODO: 设置规则发送消息"}
