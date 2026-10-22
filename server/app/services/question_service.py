# -*- coding: utf-8 -*-
"""题库管理服务：列表检索、增删改、查重、题型统计。

设计要点：
- 新增/编辑统一走 :func:`build_normalized`，复用导入时的归一化逻辑，
  保证「后台手工录入」与「JSON 导入」产出的数据结构完全一致（含 stem_norm/stem_hash）。
- 查重单独提供接口，前端可先查再存，避免保存请求里夹带「是否覆盖」这类隐式语义。
"""

from __future__ import annotations

import json
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from ..config import settings
from ..models import (
    QUESTION_TYPES,
    TYPE_JUDGE,
    TYPE_MULTIPLE,
    TYPE_SHORT,
    TYPE_SINGLE,
    Question,
)
from ..schemas import QuestionIn
from ..utils.dedup import DedupIndex
from ..utils.json_loader import (
    NormalizedQuestion,
    QuestionFormatError,
    normalize_question,
)
from ..utils.text_norm import make_preview

ORDER_NEWEST = "newest"
ORDER_OLDEST = "oldest"


class QuestionValidationError(ValueError):
    """题目内容不合法（路由层转成 400，附中文提示）。"""


def build_normalized(payload: QuestionIn) -> NormalizedQuestion:
    """把后台表单入参归一化成与导入一致的题目结构，并做业务校验。

    :raises QuestionValidationError: 题干为空 / 题型非法 / 选项或答案不符合该题型要求
    """
    title = (payload.title or "").strip()
    if not title:
        raise QuestionValidationError("题干不能为空")

    raw = {
        "id": payload.ext_id,
        "type": payload.type,
        "title": title,
        "options": [{"key": item.key, "text": item.text} for item in (payload.options or [])],
        "answer": payload.answer,
        "analysis": payload.analysis,
    }
    try:
        question = normalize_question(raw)
    except QuestionFormatError as exc:
        raise QuestionValidationError(str(exc)) from exc

    _validate(question)
    return question


class QuestionService:
    """题库的读写操作。"""

    def __init__(self, db: Session) -> None:
        self.db = db

    # ------------------------------------------------------------- 查询
    def list(
        self,
        page: int = 1,
        page_size: int = 20,
        qtype: Optional[str] = None,
        keyword: Optional[str] = None,
        order: str = ORDER_NEWEST,
    ) -> Tuple[List[Question], int]:
        """分页检索：题型 / 关键词（题干、选项、解析）。"""
        conditions = _build_conditions(qtype, keyword)
        stmt = select(Question)
        count_stmt = select(func.count(Question.id))
        for condition in conditions:
            stmt = stmt.where(condition)
            count_stmt = count_stmt.where(condition)

        order_by = _order_by(order)
        total = int(self.db.scalar(count_stmt) or 0)
        rows = (
            self.db.execute(
                stmt.order_by(*order_by).offset((page - 1) * page_size).limit(page_size)
            )
            .scalars()
            .all()
        )
        return list(rows), total

    def fetch_all(
        self,
        qtype: Optional[str] = None,
        keyword: Optional[str] = None,
        order: str = ORDER_NEWEST,
        limit: int = 50000,
    ) -> List[Question]:
        """按筛选条件取出全部题目（导出用，limit 兜底防止内存爆掉）。"""
        stmt = select(Question)
        for condition in _build_conditions(qtype, keyword):
            stmt = stmt.where(condition)
        rows = self.db.execute(stmt.order_by(*_order_by(order)).limit(limit)).scalars().all()
        return list(rows)

    def get(self, question_id: int) -> Optional[Question]:
        return self.db.get(Question, question_id)

    def type_stats(self) -> Dict[str, Any]:
        """各题型数量 + 总数。"""
        rows = self.db.execute(
            select(Question.type, func.count(Question.id)).group_by(Question.type)
        ).all()
        counts = {qtype: 0 for qtype in QUESTION_TYPES}
        for qtype, count in rows:
            counts[str(qtype)] = int(count)
        total = sum(counts.values())
        return {"total": total, "counts": counts}

    # ------------------------------------------------------------- 写入
    def create(self, payload: QuestionIn) -> Question:
        question = build_normalized(payload)
        row = self._to_row(question)
        self.db.add(row)
        self.db.commit()
        self.db.refresh(row)
        return row

    def update(self, question_id: int, payload: QuestionIn) -> Optional[Question]:
        row = self.db.get(Question, question_id)
        if row is None:
            return None

        question = build_normalized(payload)
        row.ext_id = question.ext_id or None
        row.type = question.type
        row.title = question.title
        row.options = _dump(question.options) if question.options else None
        row.answer = _dump(question.answer)
        row.analysis = question.analysis or None
        # 题干变了必须重算，否则查重索引会失准
        row.stem_norm = question.stem_norm
        row.stem_hash = question.stem_hash

        self.db.commit()
        self.db.refresh(row)
        return row

    def delete(self, question_id: int) -> bool:
        row = self.db.get(Question, question_id)
        if row is None:
            return False
        self.db.delete(row)
        self.db.commit()
        return True

    # ------------------------------------------------------------- 查重
    def check_duplicate(
        self, title: str, exclude_id: Optional[int] = None, threshold: Optional[float] = None
    ) -> Optional[Dict[str, Any]]:
        """检查题干是否与题库已有题目重复；命中返回命中的题目信息。"""
        text = (title or "").strip()
        if not text:
            return None

        question = build_normalized(QuestionIn(title=text, type=TYPE_SHORT))

        index = DedupIndex(settings.dedup_threshold if threshold is None else threshold)
        rows = self.db.execute(
            select(Question.id, Question.stem_norm, Question.stem_hash, Question.title)
        ).all()
        for qid, stem_norm, stem_hash, row_title in rows:
            if exclude_id is not None and qid == exclude_id:
                continue
            index.add(qid, stem_norm or "", stem_hash or "")

        matched = index.find_duplicate(question.stem_norm, question.stem_hash)
        if matched is None:
            return None

        matched_id, score = matched
        hit = self.db.get(Question, matched_id)
        return {
            "question_id": matched_id,
            "similarity": score,
            "preview": make_preview(hit.title if hit else "", limit=80),
        }

    # ------------------------------------------------------------- 内部
    @staticmethod
    def _to_row(question: NormalizedQuestion) -> Question:
        return Question(
            ext_id=question.ext_id or None,
            type=question.type,
            title=question.title,
            options=_dump(question.options) if question.options else None,
            answer=_dump(question.answer),
            analysis=question.analysis or None,
            stem_norm=question.stem_norm,
            stem_hash=question.stem_hash,
        )


# ------------------------------------------------------------------ 查询条件
def _build_conditions(qtype: Optional[str], keyword: Optional[str]) -> List[Any]:
    """题型 / 关键词筛选条件（列表检索与导出共用）。"""
    conditions: List[Any] = []
    if qtype:
        conditions.append(Question.type == qtype)
    if keyword:
        kw = keyword.strip()
        if kw:
            # autoescape 保证用户输入的 % _ 不会被当成通配符
            conditions.append(
                or_(
                    Question.title.contains(kw, autoescape=True),
                    Question.options.contains(kw, autoescape=True),
                    Question.analysis.contains(kw, autoescape=True),
                )
            )
    return conditions


def _order_by(order: str) -> tuple:
    if order == ORDER_OLDEST:
        return (Question.id.asc(),)
    return (Question.created_at.desc(), Question.id.desc())


# ------------------------------------------------------------------ 校验
def _validate(question: NormalizedQuestion) -> None:
    """按题型校验选项与答案（归一化之后的结构）。"""
    qtype = question.type
    options = question.options
    keys = [item["key"] for item in options]
    answer = question.answer

    if qtype in (TYPE_SINGLE, TYPE_MULTIPLE):
        if len(options) < 2:
            raise QuestionValidationError("选择题至少需要 2 个选项")
        empty = [item["key"] for item in options if not (item["text"] or "").strip()]
        if empty:
            raise QuestionValidationError(f"选项 {', '.join(empty)} 的内容不能为空")

    if qtype == TYPE_SINGLE:
        if not isinstance(answer, str) or not answer:
            raise QuestionValidationError("单选题必须指定唯一正确答案")
        if answer not in keys:
            raise QuestionValidationError(f"答案 {answer} 不在选项范围内")

    elif qtype == TYPE_MULTIPLE:
        if not isinstance(answer, list) or not answer:
            raise QuestionValidationError("多选题至少需要 1 个正确答案")
        invalid = [item for item in answer if item not in keys]
        if invalid:
            raise QuestionValidationError(f"答案 {', '.join(invalid)} 不在选项范围内")
        if len(answer) < 2:
            raise QuestionValidationError("多选题的正确答案应多于 1 个，若只有 1 个请改为单选题")

    elif qtype == TYPE_JUDGE:
        if not isinstance(answer, bool):
            raise QuestionValidationError("判断题的答案必须是「正确」或「错误」")

    elif qtype == TYPE_SHORT:
        # 简答题允许暂时不写参考答案
        if answer is None:
            question.answer = ""


def _dump(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False)
