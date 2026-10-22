# -*- coding: utf-8 -*-
"""刷题路由：抽题、提交作答、简答自评、收藏与错题本操作。

约定：
- 抽题接口不下发 answer / analysis，判分一律在服务端完成；
- 所有接口以「当前档案」为界，切换档案即切换作答数据。
"""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import current_profile
from ..models import QUESTION_TYPES, Profile
from ..schemas import (
    PracticeFavoriteOut,
    PracticeQuestionOut,
    PracticeQuestionPageOut,
    PracticeResultOut,
    PracticeSelfEvalIn,
    PracticeStatsOut,
    PracticeSubmitIn,
    ReviewPageOut,
    ReviewQuestionOut,
)
from ..services.practice_service import (
    DEFAULT_BATCH,
    MAX_BATCH,
    MODE_RECITE,
    MODE_SEQUENCE,
    ORDER_RECENT,
    PRACTICE_MODES,
    REVIEW_ORDERS,
    PracticeError,
    PracticeService,
)

router = APIRouter(prefix="/practice", tags=["practice"])


@router.get("/stats", response_model=PracticeStatsOut)
def practice_stats(
    db: Session = Depends(get_db), profile: Profile = Depends(current_profile)
) -> PracticeStatsOut:
    """当前档案的刷题概览（总题数 / 已答 / 答对 / 错题 / 收藏）。"""
    return PracticeStatsOut(**PracticeService(db, profile.id).stats())


@router.get("/questions", response_model=PracticeQuestionPageOut)
def practice_questions(
    mode: str = Query(default=MODE_SEQUENCE, description=f"练习模式：{'/'.join(PRACTICE_MODES)}"),
    type: Optional[str] = Query(default=None, description=f"题型：{'/'.join(QUESTION_TYPES)}"),
    keyword: Optional[str] = Query(default=None, description="关键词：匹配题干 / 选项"),
    count: int = Query(default=DEFAULT_BATCH, ge=1, le=MAX_BATCH, description="每批题量"),
    page: int = Query(default=1, ge=1),
    db: Session = Depends(get_db),
    profile: Profile = Depends(current_profile),
) -> PracticeQuestionPageOut:
    """按模式抽题。背题模式（recite）会带上答案与解析，其余模式不含。"""
    service = PracticeService(db, profile.id)
    try:
        rows, total = service.list_questions(
            mode=mode,
            qtype=type,
            keyword=keyword,
            count=count,
            page=page,
        )
    except PracticeError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return PracticeQuestionPageOut(
        mode=mode,
        total=total,
        items=[
            PracticeQuestionOut(**item)
            for item in service.decorate(rows, with_answer=(mode == MODE_RECITE))
        ],
    )


@router.get("/wrong", response_model=ReviewPageOut)
def list_wrong(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=200),
    type: Optional[str] = Query(default=None, description=f"题型：{'/'.join(QUESTION_TYPES)}"),
    keyword: Optional[str] = Query(default=None, description="关键词：匹配题干 / 选项"),
    order: str = Query(default=ORDER_RECENT, description=f"排序：{'/'.join(REVIEW_ORDERS)}"),
    db: Session = Depends(get_db),
    profile: Profile = Depends(current_profile),
) -> ReviewPageOut:
    """错题本分页列表（含答案与解析，供复盘查看）。"""
    items, total = PracticeService(db, profile.id).list_wrong(
        page=page,
        page_size=page_size,
        qtype=type,
        keyword=keyword,
        order=order,
    )
    return ReviewPageOut(
        total=total,
        page=page,
        page_size=page_size,
        items=[ReviewQuestionOut(**item) for item in items],
    )


@router.get("/favorites", response_model=ReviewPageOut)
def list_favorites(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=200),
    type: Optional[str] = Query(default=None, description=f"题型：{'/'.join(QUESTION_TYPES)}"),
    keyword: Optional[str] = Query(default=None, description="关键词：匹配题干 / 选项"),
    order: str = Query(default=ORDER_RECENT, description=f"排序：{'/'.join(REVIEW_ORDERS)}"),
    db: Session = Depends(get_db),
    profile: Profile = Depends(current_profile),
) -> ReviewPageOut:
    """收藏夹分页列表（含答案与解析与作答状态）。"""
    items, total = PracticeService(db, profile.id).list_favorites(
        page=page,
        page_size=page_size,
        qtype=type,
        keyword=keyword,
        order=order,
    )
    return ReviewPageOut(
        total=total,
        page=page,
        page_size=page_size,
        items=[ReviewQuestionOut(**item) for item in items],
    )


@router.post("/answer", response_model=PracticeResultOut)
def submit_answer(
    payload: PracticeSubmitIn,
    db: Session = Depends(get_db),
    profile: Profile = Depends(current_profile),
) -> PracticeResultOut:
    """提交一题作答并返回判分结果（含正确答案与解析）。"""
    service = PracticeService(db, profile.id)
    try:
        result = service.submit(
            question_id=payload.question_id,
            user_answer=payload.user_answer,
            mode=payload.mode,
            duration_ms=payload.duration_ms,
        )
    except PracticeError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return PracticeResultOut(**result)


@router.post("/self-evaluate", response_model=PracticeResultOut)
def self_evaluate(
    payload: PracticeSelfEvalIn,
    db: Session = Depends(get_db),
    profile: Profile = Depends(current_profile),
) -> PracticeResultOut:
    """简答题自评：把「待自评」补成对 / 错。"""
    service = PracticeService(db, profile.id)
    try:
        result = service.self_evaluate(
            question_id=payload.question_id,
            is_correct=payload.is_correct,
            mode=payload.mode,
        )
    except PracticeError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return PracticeResultOut(**result)


@router.post("/favorites/{question_id}/toggle", response_model=PracticeFavoriteOut)
def toggle_favorite(
    question_id: int,
    db: Session = Depends(get_db),
    profile: Profile = Depends(current_profile),
) -> PracticeFavoriteOut:
    """收藏 / 取消收藏。"""
    try:
        favorite = PracticeService(db, profile.id).toggle_favorite(question_id)
    except PracticeError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return PracticeFavoriteOut(question_id=question_id, is_favorite=favorite)


@router.delete("/wrong/{question_id}")
def remove_wrong(
    question_id: int,
    db: Session = Depends(get_db),
    profile: Profile = Depends(current_profile),
) -> dict:
    """把题目移出错题本。"""
    removed = PracticeService(db, profile.id).remove_wrong(question_id)
    if not removed:
        raise HTTPException(status_code=404, detail="该题不在错题本中")
    return {"ok": True}
