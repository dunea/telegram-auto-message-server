from fastapi import APIRouter, Depends, HTTPException

from app.api.deps import get_task_service
from app.schema.task import CreateRuleTaskRequest, CreateScheduledTaskRequest
from app.service.task_service import TaskService

router = APIRouter(prefix="/tasks", tags=["tasks"])


@router.post("/schedule")
async def create_schedule_task(
    payload: CreateScheduledTaskRequest,
    task_service: TaskService = Depends(get_task_service),
) -> dict:
    try:
        return task_service.RegisterScheduledTask(payload.model_dump())
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/rule")
async def create_rule_task(
    payload: CreateRuleTaskRequest,
    task_service: TaskService = Depends(get_task_service),
) -> dict:
    try:
        return task_service.RegisterRuleTask(payload.model_dump())
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
