"""任务管理 API 路由。

对外提供定时任务与规则任务的创建入口，实际调度由 TaskService/TaskScheduler 负责。
"""

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
    """创建定时任务。

    适用于在固定时间触发消息下发。请求体会原样转为字典交给服务层校验。

    - account_id: 发送账户 ID。
    - cron_expr: Cron 表达式，定义任务触发时间。
    - target_identifier: 目标标识（用户/群组）。
    - message_content: 可选结构化消息内容。
    - message_template: 可选模板文本；与 message_content 并存时由服务层决定优先级。

    审查关注点：
    - cron_expr 的格式正确性在服务层校验，路由层只做参数接收；
    - message_template 与 message_content 同时存在时，以服务层规则决定最终内容；
    - 400 表示任务定义不满足注册条件。

    业务校验失败时，ValueError 映射为 400。
    """
    try:
        return task_service.RegisterScheduledTask(payload.model_dump())
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/rule")
async def create_rule_task(
    payload: CreateRuleTaskRequest,
    task_service: TaskService = Depends(get_task_service),
) -> dict:
    """创建规则任务。

    适用于按规则条件触发消息动作（非固定时刻）。

    - account_id: 发送账户 ID。
    - trigger_type: 触发类型（由服务层解析与校验）。
    - condition_json: 触发条件 JSON 字符串。
    - action_json: 动作配置 JSON 字符串。
    - message_content: 可选结构化消息内容。
    - message_template: 可选模板文本；与 message_content 并存时由服务层决定优先级。

    审查关注点：
    - trigger_type、condition_json、action_json 的业务合法性由服务层统一校验；
    - 规则触发任务通常依赖外部事件输入，应重点审查条件表达式的可维护性；
    - 400 表示规则定义或动作配置未通过业务校验。

    业务校验失败时，ValueError 映射为 400。
    """
    try:
        return task_service.RegisterRuleTask(payload.model_dump())
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
