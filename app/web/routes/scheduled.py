import logging
from typing import Any
from fastapi import APIRouter, Depends, Form, Request, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db_session, get_task_service
from app.models.account import TelegramAccount
from app.models.file import FileRecord
from app.models.task import ScheduledMessageTask
from app.service.task_service import TaskService
from app.web import templates
from app.web.dependencies import get_current_user_from_cookie

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/web", tags=["web-scheduled"])


@router.get("/scheduled", response_class=HTMLResponse)
async def list_scheduled_tasks(
    request: Request,
    account_id: int | None = None,
    user_id: int = Depends(get_current_user_from_cookie),
    db_session: AsyncSession = Depends(get_db_session),
    task_service: TaskService = Depends(get_task_service),
):
    accounts = (await db_session.scalars(select(TelegramAccount).order_by(TelegramAccount.id))).all()
    accounts_map = {acc.id: acc for acc in accounts}
    
    # 账号过滤，如果 account_id 为0或空，表示无过滤
    actual_account_id = account_id if account_id and account_id > 0 else None
    
    if actual_account_id:
        tasks_data = await task_service.ListScheduledTasksByAccountId(account_id=actual_account_id, limit=100, offset=0)
        tasks_list = tasks_data["items"]
    else:
        # 获取全局所有定时发送任务汇总
        stmt = select(ScheduledMessageTask).order_by(ScheduledMessageTask.id.desc())
        tasks = (await db_session.scalars(stmt)).all()
        tasks_list = [
            {
                "task_id": int(t.id),
                "account_id": int(t.account_id),
                "cron_expr": t.cron_expr,
                "target_identifier": t.target_identifier,
                "message_template": t.message_template or "",
                "message_content_id": t.message_content_id,
                "is_active": bool(t.is_active),
                "scope_mode": t.scope_mode,
                "conversation_ids": t.conversation_ids,
                "message_ids": t.message_ids,
            }
            for t in tasks
        ]
        
    return templates.TemplateResponse(request, "scheduled/list.html", {
        "user_id": user_id,
        "tasks": tasks_list,
        "accounts": accounts,
        "accounts_map": accounts_map,
        "selected_account_id": actual_account_id or "",
    })


@router.get("/scheduled/new", response_class=HTMLResponse)
async def new_scheduled_page(
    request: Request,
    user_id: int = Depends(get_current_user_from_cookie),
    db_session: AsyncSession = Depends(get_db_session),
):
    accounts = (await db_session.scalars(select(TelegramAccount).order_by(TelegramAccount.id))).all()
    files = (await db_session.scalars(select(FileRecord).where(FileRecord.status == "uploaded"))).all()

    return templates.TemplateResponse(request, "scheduled/form.html", {
        "user_id": user_id,
        "accounts": accounts,
        "files": files,
        "task": None,
    })


@router.post("/scheduled/new")
async def create_scheduled_task(
    account_id: int = Form(...),
    cron_expr: str = Form(...),
    target_identifier: str = Form(...),
    message_template: str = Form(""),
    scope_mode: str = Form("all"),
    conversation_ids: str = Form(""),
    file_id: str = Form(""),
    user_id: int = Depends(get_current_user_from_cookie),
    db_session: AsyncSession = Depends(get_db_session),
    task_service: TaskService = Depends(get_task_service),
):
    conv_id_list = []
    if conversation_ids:
        for cid in conversation_ids.split(","):
            cid = cid.strip()
            if cid.isdigit() or (cid.startswith("-") and cid[1:].isdigit()):
                conv_id_list.append(int(cid))
                
    payload = {
        "account_id": account_id,
        "cron_expr": cron_expr,
        "target_identifier": target_identifier,
        "message_template": message_template,
        "scope_mode": scope_mode,
        "conversation_ids": conv_id_list if scope_mode == "specific" else [],
    }
    
    # 关联文件逻辑
    file_id_val = None
    if file_id and file_id.strip().isdigit():
        file_id_val = int(file_id.strip())
        
    if file_id_val:
        file_rec = await db_session.get(FileRecord, file_id_val)
        if file_rec:
            ext = file_rec.local_path.lower().split(".")[-1] if "." in file_rec.local_path else ""
            media_type = "image" if ext in ["jpg", "jpeg", "png", "gif", "webp"] else "file"

            payload["message_content"] = {
                "content_type": "media",
                "media_type": media_type,
                "media_url": file_rec.s3_url or file_rec.local_path,
                "media_key": file_rec.s3_key or "",
                "text_content": message_template,
            }
            payload["content_type"] = "media"
            payload["media_type"] = media_type
            payload["media_url"] = file_rec.s3_url or file_rec.local_path
            payload["media_key"] = file_rec.s3_key or ""
            payload["text_content"] = message_template
    else:
        # 普通文本消息
        payload["content_type"] = "text"
        payload["text_content"] = message_template

    try:
        await task_service.RegisterScheduledTask(payload)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return RedirectResponse(url="/web/scheduled", status_code=303)


@router.get("/scheduled/{task_id}/edit", response_class=HTMLResponse)
async def edit_scheduled_page(
    task_id: int,
    request: Request,
    user_id: int = Depends(get_current_user_from_cookie),
    db_session: AsyncSession = Depends(get_db_session),
    task_service: TaskService = Depends(get_task_service),
):
    try:
        task = await task_service.GetScheduledTaskById(task_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="定时发送任务不存在")
        
    accounts = (await db_session.scalars(select(TelegramAccount).order_by(TelegramAccount.id))).all()
    files = (await db_session.scalars(select(FileRecord).where(FileRecord.status == "uploaded"))).all()
    # 我们根据 message_content_id 查一下对应的 message_content
    from app.models.message import MessageContent
    selected_file_id = None
    if task.get("message_content_id"):
        content_obj = await db_session.get(MessageContent, task["message_content_id"])
        if content_obj and content_obj.media_url:
            file_rec = await db_session.scalar(
                select(FileRecord).where(
                    (FileRecord.s3_url == content_obj.media_url) |
                    (FileRecord.local_path == content_obj.media_url)
                )
            )
            if file_rec:
                selected_file_id = file_rec.id
                
    conv_ids_str = ",".join(map(str, task["conversation_ids"] or [])) if task.get("conversation_ids") else ""
    
    return templates.TemplateResponse(request, "scheduled/form.html", {
        "user_id": user_id,
        "accounts": accounts,
        "files": files,
        "task": task,
        "conv_ids_str": conv_ids_str,
        "selected_file_id": selected_file_id,
    })


@router.post("/scheduled/{task_id}/edit")
async def update_scheduled_task(
    task_id: int,
    account_id: int = Form(...),
    cron_expr: str = Form(...),
    target_identifier: str = Form(...),
    message_template: str = Form(""),
    scope_mode: str = Form("all"),
    conversation_ids: str = Form(""),
    file_id: str = Form(""),
    user_id: int = Depends(get_current_user_from_cookie),
    db_session: AsyncSession = Depends(get_db_session),
    task_service: TaskService = Depends(get_task_service),
):
    conv_id_list = []
    if conversation_ids:
        for cid in conversation_ids.split(","):
            cid = cid.strip()
            if cid.isdigit() or (cid.startswith("-") and cid[1:].isdigit()):
                conv_id_list.append(int(cid))
                
    payload = {
        "account_id": account_id,
        "cron_expr": cron_expr,
        "target_identifier": target_identifier,
        "message_template": message_template,
        "scope_mode": scope_mode,
        "conversation_ids": conv_id_list if scope_mode == "specific" else [],
    }
    
    file_id_val = None
    if file_id and file_id.strip().isdigit():
        file_id_val = int(file_id.strip())
        
    if file_id_val:
        file_rec = await db_session.get(FileRecord, file_id_val)
        if file_rec:
            ext = file_rec.local_path.lower().split(".")[-1] if "." in file_rec.local_path else ""
            media_type = "image" if ext in ["jpg", "jpeg", "png", "gif", "webp"] else "file"
            
            payload["message_content"] = {
                "content_type": "media",
                "media_type": media_type,
                "media_url": file_rec.s3_url or file_rec.local_path,
                "media_key": file_rec.s3_key or "",
                "text_content": message_template,
            }
            payload["content_type"] = "media"
            payload["media_type"] = media_type
            payload["media_url"] = file_rec.s3_url or file_rec.local_path
            payload["media_key"] = file_rec.s3_key or ""
            payload["text_content"] = message_template
    else:
        payload["content_type"] = "text"
        payload["text_content"] = message_template

    try:
        await task_service.UpdateScheduledTask(task_id, payload)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
        
    return RedirectResponse(url="/web/scheduled", status_code=303)


@router.post("/scheduled/{task_id}/toggle-active", response_class=HTMLResponse)
async def toggle_scheduled_active(
    task_id: int,
    user_id: int = Depends(get_current_user_from_cookie),
    task_service: TaskService = Depends(get_task_service),
):
    try:
        task = await task_service.GetScheduledTaskById(task_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="定时发送任务不存在")
        
    new_active = not task["is_active"]
    updated_task = await task_service.SetScheduledTaskActive(task_id, is_active=new_active)
    
    label = "● 启用中" if updated_task["is_active"] else "○ 已禁用"
    color_class = "text-green-600 font-bold" if updated_task["is_active"] else "text-red-500 font-bold"
    
    return HTMLResponse(f"""
        <button hx-post="/web/scheduled/{task_id}/toggle-active"
                hx-target="this"
                hx-swap="outerHTML"
                class="inline-flex items-center px-3 py-1.5 border border-gray-300 shadow-sm text-xs font-medium rounded text-gray-700 bg-white hover:bg-gray-50 focus:outline-none">
            <span class="{color_class}">{label}</span>
        </button>
    """)


@router.post("/scheduled/{task_id}/delete")
async def delete_scheduled_task(
    task_id: int,
    user_id: int = Depends(get_current_user_from_cookie),
    task_service: TaskService = Depends(get_task_service),
):
    try:
        await task_service.SoftDeleteScheduledTask(task_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="定时发送任务不存在")
    return RedirectResponse(url="/web/scheduled", status_code=303)


@router.get("/scheduled/{task_id}/messages", response_class=HTMLResponse)
async def scheduled_messages_page(
    task_id: int,
    request: Request,
    user_id: int = Depends(get_current_user_from_cookie),
    db_session: AsyncSession = Depends(get_db_session),
    task_service: TaskService = Depends(get_task_service),
):
    try:
        task = await task_service.GetScheduledTaskById(task_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="定时发送任务不存在")
        
    from sqlalchemy import select
    from app.models.message import MessageContent
    from app.models.file import FileRecord
    from app.models.account import TelegramAccount

    accounts = (await db_session.scalars(select(TelegramAccount).order_by(TelegramAccount.id))).all()
    accounts_map = {acc.id: acc for acc in accounts}
    account = accounts_map.get(task["account_id"])
    files = (await db_session.scalars(select(FileRecord).where(FileRecord.status == "uploaded"))).all()

    # 查出当前定时任务绑定的多消息池内容
    task_message_pool = []
    if task.get("message_ids") and isinstance(task.get("message_ids"), list):
        for m_id in task["message_ids"]:
            content_obj = await db_session.get(MessageContent, m_id)
            if content_obj:
                selected_file_id = ""
                if content_obj.media_url:
                    file_rec = await db_session.scalar(
                        select(FileRecord).where(
                            (FileRecord.s3_url == content_obj.media_url) |
                            (FileRecord.local_path == content_obj.media_url)
                        )
                    )
                    if file_rec:
                        selected_file_id = str(file_rec.id)
                task_message_pool.append({
                    "text": content_obj.text_content or content_obj.caption or "",
                    "file_record_id": selected_file_id
                })

    return templates.TemplateResponse(request, "scheduled/messages.html", {
        "user_id": user_id,
        "task": task,
        "account": account,
        "files": files,
        "task_message_pool": task_message_pool,
    })


@router.post("/scheduled/{task_id}/messages")
async def update_scheduled_messages(
    task_id: int,
    scheduled_messages_text: list[str] = Form(None),
    scheduled_messages_file_id: list[str] = Form(None),
    user_id: int = Depends(get_current_user_from_cookie),
    task_service: TaskService = Depends(get_task_service),
):
    messages_payload = []
    if scheduled_messages_text:
        for idx, text in enumerate(scheduled_messages_text):
            text_str = text.strip()
            file_id_val = None
            if scheduled_messages_file_id and idx < len(scheduled_messages_file_id):
                fid_str = str(scheduled_messages_file_id[idx]).strip()
                if fid_str and fid_str.isdigit():
                    file_id_val = int(fid_str)
            if text_str or file_id_val:
                messages_payload.append({
                    "text": text_str,
                    "file_record_id": file_id_val
                })

    try:
        await task_service.UpdateScheduledTaskMessagePool(
            task_id=task_id,
            messages_payload=messages_payload,
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
        
    return RedirectResponse(url="/web/scheduled", status_code=303)

