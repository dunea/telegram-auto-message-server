"""回复消息（自动回复规则）API 路由。"""

from fastapi import APIRouter, Depends, HTTPException, Query

from app.api.deps import get_auto_reply_service, get_current_user
from app.schema.auto_reply_rule import (
    AutoReplyRuleListResponse,
    AutoReplyRuleResponse,
    CreateAutoReplyRuleRequest,
    UpdateAutoReplyRuleActiveRequest,
    UpdateAutoReplyRuleRequest,
)
from app.service.auto_reply_service import AutoReplyService

router = APIRouter(prefix="/auto-reply-rules", tags=["auto-reply-rules"], dependencies=[Depends(get_current_user)])


@router.post("", response_model=AutoReplyRuleResponse)
async def create_auto_reply_rule(
    payload: CreateAutoReplyRuleRequest,
    auto_reply_service: AutoReplyService = Depends(get_auto_reply_service),
) -> AutoReplyRuleResponse:
    """新增回复消息规则。"""
    try:
        result = auto_reply_service.CreateRule(
            account_id=payload.account_id,
            trigger_keyword=payload.trigger_keyword,
            reply_content=payload.reply_content,
        )
        return AutoReplyRuleResponse(**result)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("", response_model=AutoReplyRuleListResponse)
async def list_auto_reply_rules(
    account_id: int = Query(..., ge=1),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    auto_reply_service: AutoReplyService = Depends(get_auto_reply_service),
) -> AutoReplyRuleListResponse:
    """查询回复消息规则列表。"""
    result = auto_reply_service.ListRulesByAccountId(account_id=account_id, limit=limit, offset=offset)
    return AutoReplyRuleListResponse(**result)


@router.get("/{rule_id}", response_model=AutoReplyRuleResponse)
async def get_auto_reply_rule(
    rule_id: int,
    auto_reply_service: AutoReplyService = Depends(get_auto_reply_service),
) -> AutoReplyRuleResponse:
    """查询单个回复消息规则。"""
    try:
        return AutoReplyRuleResponse(**auto_reply_service.GetRuleById(rule_id=rule_id))
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.put("/{rule_id}", response_model=AutoReplyRuleResponse)
async def update_auto_reply_rule(
    rule_id: int,
    payload: UpdateAutoReplyRuleRequest,
    auto_reply_service: AutoReplyService = Depends(get_auto_reply_service),
) -> AutoReplyRuleResponse:
    """修改回复消息规则。"""
    try:
        result = auto_reply_service.UpdateRule(
            rule_id=rule_id,
            trigger_keyword=payload.trigger_keyword,
            reply_content=payload.reply_content,
        )
        return AutoReplyRuleResponse(**result)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.patch("/{rule_id}/active", response_model=AutoReplyRuleResponse)
async def update_auto_reply_rule_active(
    rule_id: int,
    payload: UpdateAutoReplyRuleActiveRequest,
    auto_reply_service: AutoReplyService = Depends(get_auto_reply_service),
) -> AutoReplyRuleResponse:
    """启用或停用回复消息规则。"""
    try:
        result = auto_reply_service.SetRuleActive(rule_id=rule_id, is_active=payload.is_active)
        return AutoReplyRuleResponse(**result)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.delete("/{rule_id}")
async def delete_auto_reply_rule(
    rule_id: int,
    auto_reply_service: AutoReplyService = Depends(get_auto_reply_service),
) -> dict:
    """软删除回复消息规则。"""
    try:
        return auto_reply_service.SoftDeleteRule(rule_id=rule_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
