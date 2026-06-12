import logging
from typing import Any
from fastapi import APIRouter, Depends, Form, Request, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db_session, get_auto_reply_service
from app.models.account import TelegramAccount
from app.models.file import FileRecord
from app.schema.reply_message import ReplyMessageCreate, ReplyMessageMediaItem
from app.service.auto_reply_service import AutoReplyService
from app.web import templates
from app.web.dependencies import get_current_user_from_cookie

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/web", tags=["web-auto-reply"])


@router.get("/auto-reply", response_class=HTMLResponse)
async def list_auto_reply_rules(
    request: Request,
    account_id: int | None = None,
    user_id: int = Depends(get_current_user_from_cookie),
    db_session: AsyncSession = Depends(get_db_session),
    auto_reply_service: AutoReplyService = Depends(get_auto_reply_service),
):
    accounts = (await db_session.scalars(select(TelegramAccount).order_by(TelegramAccount.id))).all()
    accounts_map = {acc.id: acc for acc in accounts}
    
    # 如果 account_id 为0或空，我们视其为无过滤
    actual_account_id = account_id if account_id and account_id > 0 else None
    
    # 获取过滤后的规则列表
    rules_data = await auto_reply_service.ListRules(account_id=actual_account_id, limit=100, offset=0)
    
    return templates.TemplateResponse(request, "auto_reply/list.html", {
        "user_id": user_id,
        "rules": rules_data["items"],
        "accounts": accounts,
        "accounts_map": accounts_map,
        "selected_account_id": actual_account_id or "",
    })


@router.get("/auto-reply/new", response_class=HTMLResponse)
async def new_rule_page(
    request: Request,
    user_id: int = Depends(get_current_user_from_cookie),
    db_session: AsyncSession = Depends(get_db_session),
):
    accounts = (await db_session.scalars(select(TelegramAccount).order_by(TelegramAccount.id))).all()
    files = (await db_session.scalars(select(FileRecord).where(FileRecord.status == "uploaded"))).all()

    return templates.TemplateResponse(request, "auto_reply/form.html", {
        "user_id": user_id,
        "accounts": accounts,
        "files": files,
        "rule": None,
    })


@router.post("/auto-reply/new")
async def create_rule(
    account_id: int = Form(...),
    trigger_mode: str = Form("keyword"),
    trigger_keyword: str = Form(""),
    keywords: str = Form(""),
    reply_content: str = Form(""),
    scope_mode: str = Form("all"),
    conversation_ids: str = Form(""),
    reply_messages_text: list[str] = Form(None),
    reply_messages_file_id: list[str] = Form(None),
    user_id: int = Depends(get_current_user_from_cookie),
    auto_reply_service: AutoReplyService = Depends(get_auto_reply_service),
):
    kw_list = [k.strip() for k in keywords.split(",") if k.strip()] if keywords else []
    conv_id_list = []
    if conversation_ids:
        for cid in conversation_ids.split(","):
            cid = cid.strip()
            if cid.isdigit() or (cid.startswith("-") and cid[1:].isdigit()):
                conv_id_list.append(int(cid))
                
    reply_msgs_objs = []
    if reply_messages_text:
        for idx, text in enumerate(reply_messages_text):
            text_str = text.strip()
            file_id_val = None
            if reply_messages_file_id and idx < len(reply_messages_file_id):
                fid_str = str(reply_messages_file_id[idx]).strip()
                if fid_str and fid_str.isdigit():
                    file_id_val = int(fid_str)
            if text_str or file_id_val:
                media_items = []
                if file_id_val:
                    media_items.append(ReplyMessageMediaItem(file_record_id=file_id_val, sort_order=0))
                reply_msgs_objs.append(ReplyMessageCreate(
                    text=text_str,
                    sort_order=idx,
                    media=media_items
                ))
                
    try:
        await auto_reply_service.CreateRule(
            account_id=account_id,
            trigger_keyword=trigger_keyword,
            reply_content=reply_content,
            trigger_mode=trigger_mode,
            keywords=kw_list if trigger_mode == "keyword" else [],
            scope_mode=scope_mode,
            conversation_ids=conv_id_list if scope_mode == "specific" else [],
            reply_messages=reply_msgs_objs,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
        
    return RedirectResponse(url="/web/auto-reply", status_code=303)


@router.get("/auto-reply/{rule_id}/edit", response_class=HTMLResponse)
async def edit_rule_page(
    rule_id: int,
    request: Request,
    user_id: int = Depends(get_current_user_from_cookie),
    db_session: AsyncSession = Depends(get_db_session),
    auto_reply_service: AutoReplyService = Depends(get_auto_reply_service),
):
    try:
        rule = await auto_reply_service.GetRuleById(rule_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="规则不存在")
        
    accounts = (await db_session.scalars(select(TelegramAccount).order_by(TelegramAccount.id))).all()
    files = (await db_session.scalars(select(FileRecord).where(FileRecord.status == "uploaded"))).all()
    
    keywords_str = ",".join(rule["keywords"] or []) if rule["keywords"] else ""
    conv_ids_str = ",".join(map(str, rule["conversation_ids"] or [])) if rule["conversation_ids"] else ""
    
    return templates.TemplateResponse(request, "auto_reply/form.html", {
        "user_id": user_id,
        "accounts": accounts,
        "files": files,
        "rule": rule,
        "keywords_str": keywords_str,
        "conv_ids_str": conv_ids_str,
    })


@router.post("/auto-reply/{rule_id}/edit")
async def update_rule(
    rule_id: int,
    account_id: int = Form(...),
    trigger_mode: str = Form("keyword"),
    trigger_keyword: str = Form(""),
    keywords: str = Form(""),
    reply_content: str = Form(""),
    scope_mode: str = Form("all"),
    conversation_ids: str = Form(""),
    reply_messages_text: list[str] = Form(None),
    reply_messages_file_id: list[str] = Form(None),
    user_id: int = Depends(get_current_user_from_cookie),
    auto_reply_service: AutoReplyService = Depends(get_auto_reply_service),
):
    kw_list = [k.strip() for k in keywords.split(",") if k.strip()] if keywords else []
    conv_id_list = []
    if conversation_ids:
        for cid in conversation_ids.split(","):
            cid = cid.strip()
            if cid.isdigit() or (cid.startswith("-") and cid[1:].isdigit()):
                conv_id_list.append(int(cid))
                
    reply_msgs_objs = []
    if reply_messages_text:
        for idx, text in enumerate(reply_messages_text):
            text_str = text.strip()
            file_id_val = None
            if reply_messages_file_id and idx < len(reply_messages_file_id):
                fid_str = str(reply_messages_file_id[idx]).strip()
                if fid_str and fid_str.isdigit():
                    file_id_val = int(fid_str)
            if text_str or file_id_val:
                media_items = []
                if file_id_val:
                    media_items.append(ReplyMessageMediaItem(file_record_id=file_id_val, sort_order=0))
                reply_msgs_objs.append(ReplyMessageCreate(
                    text=text_str,
                    sort_order=idx,
                    media=media_items
                ))
                
    try:
        await auto_reply_service.UpdateRule(
            rule_id=rule_id,
            trigger_keyword=trigger_keyword,
            reply_content=reply_content,
            trigger_mode=trigger_mode,
            keywords=kw_list if trigger_mode == "keyword" else [],
            scope_mode=scope_mode,
            conversation_ids=conv_id_list if scope_mode == "specific" else [],
            reply_messages=reply_msgs_objs,
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
        
    return RedirectResponse(url="/web/auto-reply", status_code=303)


@router.post("/auto-reply/{rule_id}/toggle-active", response_class=HTMLResponse)
async def toggle_rule_active(
    rule_id: int,
    user_id: int = Depends(get_current_user_from_cookie),
    auto_reply_service: AutoReplyService = Depends(get_auto_reply_service),
):
    try:
        rule = await auto_reply_service.GetRuleById(rule_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="规则不存在")
    
    new_active = not rule["is_active"]
    updated_rule = await auto_reply_service.SetRuleActive(rule_id, is_active=new_active)
    
    label = "● 启用中" if updated_rule["is_active"] else "○ 已禁用"
    color_class = "text-green-600 font-bold" if updated_rule["is_active"] else "text-red-500 font-bold"
    
    return HTMLResponse(f"""
        <button hx-post="/web/auto-reply/{rule_id}/toggle-active"
                hx-target="this"
                hx-swap="outerHTML"
                class="inline-flex items-center px-3 py-1.5 border border-gray-300 shadow-sm text-xs font-medium rounded text-gray-700 bg-white hover:bg-gray-50 focus:outline-none">
            <span class="{color_class}">{label}</span>
        </button>
    """)


@router.post("/auto-reply/{rule_id}/delete")
async def delete_rule(
    rule_id: int,
    user_id: int = Depends(get_current_user_from_cookie),
    auto_reply_service: AutoReplyService = Depends(get_auto_reply_service),
):
    try:
        await auto_reply_service.SoftDeleteRule(rule_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="规则不存在")
    return RedirectResponse(url="/web/auto-reply", status_code=303)


@router.get("/auto-reply/{rule_id}/messages", response_class=HTMLResponse)
async def rule_messages_page(
    rule_id: int,
    request: Request,
    user_id: int = Depends(get_current_user_from_cookie),
    db_session: AsyncSession = Depends(get_db_session),
    auto_reply_service: AutoReplyService = Depends(get_auto_reply_service),
):
    try:
        rule = await auto_reply_service.GetRuleById(rule_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="规则不存在")
        
    accounts = (await db_session.scalars(select(TelegramAccount).order_by(TelegramAccount.id))).all()
    accounts_map = {acc.id: acc for acc in accounts}
    account = accounts_map.get(rule["account_id"])
    files = (await db_session.scalars(select(FileRecord).where(FileRecord.status == "uploaded"))).all()
    
    return templates.TemplateResponse(request, "auto_reply/messages.html", {
        "user_id": user_id,
        "rule": rule,
        "account": account,
        "files": files,
    })


@router.post("/auto-reply/{rule_id}/messages")
async def update_rule_messages(
    rule_id: int,
    reply_messages_text: list[str] = Form(None),
    reply_messages_file_id: list[str] = Form(None),
    user_id: int = Depends(get_current_user_from_cookie),
    auto_reply_service: AutoReplyService = Depends(get_auto_reply_service),
):
    reply_msgs_objs = []
    if reply_messages_text:
        for idx, text in enumerate(reply_messages_text):
            text_str = text.strip()
            file_id_val = None
            if reply_messages_file_id and idx < len(reply_messages_file_id):
                fid_str = str(reply_messages_file_id[idx]).strip()
                if fid_str and fid_str.isdigit():
                    file_id_val = int(fid_str)
            if text_str or file_id_val:
                media_items = []
                if file_id_val:
                    media_items.append(ReplyMessageMediaItem(file_record_id=file_id_val, sort_order=0))
                reply_msgs_objs.append(ReplyMessageCreate(
                    text=text_str,
                    sort_order=idx,
                    media=media_items
                ))
                
    try:
        await auto_reply_service.UpdateRule(
            rule_id=rule_id,
            reply_messages=reply_msgs_objs,
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
        
    return RedirectResponse(url="/web/auto-reply", status_code=303)
