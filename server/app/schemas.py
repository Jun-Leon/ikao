# -*- coding: utf-8 -*-
"""API 出入参模型（Pydantic v2）。"""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any, List, Optional

from pydantic import BaseModel, Field

from .models import QUESTION_TYPES, TYPE_SINGLE


# ------------------------------------------------------------------ 通用
class HealthOut(BaseModel):
    status: str = "ok"
    app: str
    version: str
    database: str
    question_count: int = 0


class MetaOut(BaseModel):
    """前端启动时拉取的基础信息。"""

    app_name: str
    version: str
    dedup_threshold: float
    question_count: int
    current_profile_id: Optional[int] = None
    current_profile_name: Optional[str] = None


# ------------------------------------------------------------------ 题目
class OptionItem(BaseModel):
    key: str
    text: str = ""


class QuestionOut(BaseModel):
    id: int
    ext_id: Optional[str] = None
    type: str
    title: str
    options: List[OptionItem] = Field(default_factory=list)
    answer: Any = None
    analysis: Optional[str] = None
    created_at: Optional[datetime] = None

    @classmethod
    def from_row(cls, row) -> "QuestionOut":
        """从 ORM 行构造（options / answer 存的是 JSON 字符串）。"""
        return cls(
            id=row.id,
            ext_id=row.ext_id,
            type=row.type,
            title=row.title,
            options=_load_json(row.options, []),
            answer=_load_json(row.answer, None),
            analysis=row.analysis,
            created_at=row.created_at,
        )


class QuestionIn(BaseModel):
    """后台新增 / 编辑题目的入参（answer 结构随题型变化）。"""

    ext_id: Optional[str] = None
    type: str = Field(default=TYPE_SINGLE, description=f"题型：{'/'.join(QUESTION_TYPES)}")
    title: str = Field(default="", description="题干，支持 Markdown 与 LaTeX")
    options: List[OptionItem] = Field(default_factory=list)
    answer: Any = Field(default=None, description='single→"A"；multiple→["A","B"]；judge→true/false；short→文本')
    analysis: Optional[str] = None


class QuestionPageOut(BaseModel):
    total: int
    page: int
    page_size: int
    items: List[QuestionOut]


class QuestionTypeStatOut(BaseModel):
    """题库题型分布，用于列表页顶部统计。"""

    total: int
    counts: dict


class DuplicateCheckIn(BaseModel):
    title: str = Field(default="", description="待检查的题干")
    exclude_id: Optional[int] = Field(default=None, description="编辑场景下排除自身")


class DuplicateHitOut(BaseModel):
    question_id: int
    similarity: float
    preview: Optional[str] = None


class DuplicateCheckOut(BaseModel):
    duplicate: Optional[DuplicateHitOut] = None


# ------------------------------------------------------------------ 导入日志
class ImportLogOut(BaseModel):
    id: int
    source_name: str
    total: int
    imported: int
    duplicated: int
    failed: int
    threshold: float
    status: str
    message: Optional[str] = None
    created_at: Optional[datetime] = None

    @classmethod
    def from_row(cls, row) -> "ImportLogOut":
        return cls(
            id=row.id,
            source_name=row.source_name,
            total=row.total,
            imported=row.imported,
            duplicated=row.duplicated,
            failed=row.failed,
            threshold=row.threshold,
            status=row.status,
            message=row.message,
            created_at=row.created_at,
        )


class ImportLogItemOut(BaseModel):
    id: int
    row_index: int
    status: str
    reason: Optional[str] = None
    question_id: Optional[int] = None
    matched_question_id: Optional[int] = None
    similarity: Optional[float] = None
    title_preview: Optional[str] = None

    @classmethod
    def from_row(cls, row) -> "ImportLogItemOut":
        return cls(
            id=row.id,
            row_index=row.row_index,
            status=row.status,
            reason=row.reason,
            question_id=row.question_id,
            matched_question_id=row.matched_question_id,
            similarity=row.similarity,
            title_preview=row.title_preview,
        )


class ImportLogPageOut(BaseModel):
    total: int
    page: int
    page_size: int
    items: List[ImportLogOut]


class ImportLogDetailOut(BaseModel):
    log: ImportLogOut
    items_total: int
    page: int
    page_size: int
    items: List[ImportLogItemOut]


class ImportResultOut(BaseModel):
    """导入接口返回。"""

    log_id: int
    source_name: str
    total: int
    imported: int
    duplicated: int
    failed: int
    threshold: float
    status: str
    message: Optional[str] = None


# ------------------------------------------------------------------ 刷题
class PracticeQuestionOut(BaseModel):
    """刷题用题目：默认不含 answer / analysis，避免答案提前下发到前端。

    仅「背题模式（recite）」会带上 answer / analysis，此时前端直接展示答案与解析。
    """

    id: int
    ext_id: Optional[str] = None
    type: str
    title: str
    options: List[OptionItem] = Field(default_factory=list)
    practice_count: int = 0
    wrong_count: int = 0
    is_favorite: bool = False
    answer: Optional[Any] = None
    analysis: Optional[str] = None


class PracticeQuestionPageOut(BaseModel):
    mode: str
    total: int
    items: List[PracticeQuestionOut]


class PracticeSubmitIn(BaseModel):
    question_id: int
    user_answer: Any = Field(default=None, description='single→"A"；multiple→["A","B"]；judge→true/false；short→文本')
    mode: str = Field(default="sequence", description="sequence/random/wrong/favorite")
    duration_ms: int = Field(default=0, ge=0, description="本题用时（毫秒）")


class PracticeSelfEvalIn(BaseModel):
    """简答题自评。"""

    question_id: int
    is_correct: bool
    mode: str = "sequence"


class PracticeStateOut(BaseModel):
    practice_count: int = 0
    wrong_count: int = 0
    correct_streak: int = 0
    last_correct: Optional[bool] = None
    is_favorite: bool = False


class PracticeResultOut(BaseModel):
    question_id: int
    is_correct: Optional[bool] = Field(default=None, description="None 表示简答题待自评")
    correct_answer: Any = None
    analysis: Optional[str] = None
    need_self_eval: bool = False
    state: PracticeStateOut


class PracticeStatsOut(BaseModel):
    total: int = 0
    answered: int = 0
    correct: int = 0
    wrong: int = 0
    favorite: int = 0


class PracticeFavoriteOut(BaseModel):
    question_id: int
    is_favorite: bool


class ReviewQuestionOut(BaseModel):
    """错题本 / 收藏夹的行：带答案与解析，供复盘查看。"""

    id: int
    ext_id: Optional[str] = None
    type: str
    title: str
    options: List[OptionItem] = Field(default_factory=list)
    answer: Any = None
    analysis: Optional[str] = None
    practice_count: int = 0
    wrong_count: int = 0
    correct_streak: int = 0
    last_correct: Optional[bool] = None
    last_answer: Any = None
    last_answered_at: Optional[datetime] = None
    marked_at: Optional[datetime] = Field(default=None, description="收藏时间 / 最近作答时间")
    is_favorite: bool = True


class ReviewPageOut(BaseModel):
    total: int
    page: int
    page_size: int
    items: List[ReviewQuestionOut]


# ------------------------------------------------------------------ 统计看板
class StatsOverviewOut(BaseModel):
    total_questions: int = 0
    answered: int = 0
    correct: int = 0
    wrong: int = 0
    unanswered: int = 0
    favorite: int = 0
    accuracy: Optional[float] = None
    attempts: int = 0
    scored: int = 0
    study_days: int = 0
    streak_days: int = 0
    duration_ms: int = 0


class StatsTypeOut(BaseModel):
    type: str
    label: str
    total: int = 0
    answered: int = 0
    wrong: int = 0
    attempts: int = 0
    correct: int = 0
    scored: int = 0
    accuracy: Optional[float] = None


class StatsModeOut(BaseModel):
    mode: str
    label: str
    attempts: int = 0


class StatsTrendOut(BaseModel):
    date: str
    attempts: int = 0
    correct: int = 0
    accuracy: Optional[float] = None


class StatsTopWrongOut(BaseModel):
    question_id: int
    type: str
    title: str
    wrong_count: int = 0
    last_correct: Optional[bool] = None


class StatsBoardOut(BaseModel):
    overview: StatsOverviewOut
    by_type: List[StatsTypeOut] = Field(default_factory=list)
    by_mode: List[StatsModeOut] = Field(default_factory=list)
    trend: List[StatsTrendOut] = Field(default_factory=list)
    top_wrong: List[StatsTopWrongOut] = Field(default_factory=list)


# ------------------------------------------------------------------ 档案
class ProfileOut(BaseModel):
    id: int
    name: str
    is_default: bool
    created_at: Optional[datetime] = None

    @classmethod
    def from_row(cls, row) -> "ProfileOut":
        return cls(id=row.id, name=row.name, is_default=row.is_default, created_at=row.created_at)


class ProfileCreateIn(BaseModel):
    name: str = Field(min_length=1, max_length=32)


def _load_json(raw: Optional[str], default: Any) -> Any:
    """安全地把数据库里的 JSON 字符串还原成对象。"""
    if raw in (None, ""):
        return default
    try:
        return json.loads(raw)
    except (TypeError, ValueError):
        return default
