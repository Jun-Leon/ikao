# -*- coding: utf-8 -*-
"""题库管理路由：列表检索、详情、增删改、查重、题型统计、导出 CSV。

注意路由声明顺序：/stats、/export、/check-duplicate 这类静态路径
必须放在 /{question_id} 之前，否则会被当成路径参数吞掉。
"""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import QUESTION_TYPES
from ..schemas import (
    DuplicateCheckIn,
    DuplicateCheckOut,
    DuplicateHitOut,
    QuestionIn,
    QuestionOut,
    QuestionPageOut,
    QuestionTypeStatOut,
)
from ..services.question_service import (
    ORDER_NEWEST,
    ORDER_OLDEST,
    QuestionService,
    QuestionValidationError,
)
from ..utils.table_io import CSV_MEDIA_TYPE, build_questions_csv

router = APIRouter(prefix="/questions", tags=["questions"])


@router.get("", response_model=QuestionPageOut)
def list_questions(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
    type: Optional[str] = Query(default=None, description=f"题型：{'/'.join(QUESTION_TYPES)}"),
    keyword: Optional[str] = Query(default=None, description="关键词：匹配题干 / 选项 / 解析"),
    order: str = Query(default=ORDER_NEWEST, description=f"{ORDER_NEWEST} / {ORDER_OLDEST}"),
    db: Session = Depends(get_db),
) -> QuestionPageOut:
    """题目分页列表（后台管理用，含答案与解析）。"""
    service = QuestionService(db)
    rows, total = service.list(
        page=page,
        page_size=page_size,
        qtype=type,
        keyword=keyword,
        order=order,
    )
    return QuestionPageOut(
        total=total,
        page=page,
        page_size=page_size,
        items=[QuestionOut.from_row(row) for row in rows],
    )


@router.get("/stats", response_model=QuestionTypeStatOut)
def question_stats(db: Session = Depends(get_db)) -> QuestionTypeStatOut:
    """题库题型分布。"""
    data = QuestionService(db).type_stats()
    return QuestionTypeStatOut(total=data["total"], counts=data["counts"])


@router.get("/export")
def export_questions(
    type: Optional[str] = Query(default=None, description=f"题型：{'/'.join(QUESTION_TYPES)}"),
    keyword: Optional[str] = Query(default=None, description="关键词：匹配题干 / 选项 / 解析"),
    order: str = Query(default=ORDER_NEWEST, description=f"{ORDER_NEWEST} / {ORDER_OLDEST}"),
    db: Session = Depends(get_db),
) -> Response:
    """按当前筛选条件导出题库为 CSV（列格式与导入模板一致，可改完再导入）。"""
    rows = QuestionService(db).fetch_all(qtype=type, keyword=keyword, order=order)
    content = build_questions_csv(rows)
    return Response(
        content=content,
        media_type=CSV_MEDIA_TYPE,
        headers={
            "Content-Disposition": 'attachment; filename="ikao-questions.csv"',
            "Content-Length": str(len(content)),
        },
    )


@router.post("/check-duplicate", response_model=DuplicateCheckOut)
def check_duplicate(payload: DuplicateCheckIn, db: Session = Depends(get_db)) -> DuplicateCheckOut:
    """按题干相似度查重（新增/编辑保存前调用）。"""
    try:
        hit = QuestionService(db).check_duplicate(payload.title, exclude_id=payload.exclude_id)
    except QuestionValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    if hit is None:
        return DuplicateCheckOut(duplicate=None)
    return DuplicateCheckOut(duplicate=DuplicateHitOut(**hit))


@router.get("/{question_id}", response_model=QuestionOut)
def get_question(question_id: int, db: Session = Depends(get_db)) -> QuestionOut:
    """题目详情。"""
    row = QuestionService(db).get(question_id)
    if row is None:
        raise HTTPException(status_code=404, detail="题目不存在")
    return QuestionOut.from_row(row)


@router.post("", response_model=QuestionOut, status_code=201)
def create_question(payload: QuestionIn, db: Session = Depends(get_db)) -> QuestionOut:
    """新增题目。"""
    try:
        row = QuestionService(db).create(payload)
    except QuestionValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return QuestionOut.from_row(row)


@router.put("/{question_id}", response_model=QuestionOut)
def update_question(
    question_id: int, payload: QuestionIn, db: Session = Depends(get_db)
) -> QuestionOut:
    """编辑题目（会重算查重用的题干指纹）。"""
    try:
        row = QuestionService(db).update(question_id, payload)
    except QuestionValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if row is None:
        raise HTTPException(status_code=404, detail="题目不存在")
    return QuestionOut.from_row(row)


@router.delete("/{question_id}")
def delete_question(question_id: int, db: Session = Depends(get_db)) -> dict:
    """删除题目（同时清理该题的作答记录、收藏）。"""
    if not QuestionService(db).delete(question_id):
        raise HTTPException(status_code=404, detail="题目不存在")
    return {"ok": True}
