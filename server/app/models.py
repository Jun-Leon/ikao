# -*- coding: utf-8 -*-
"""SQLite 数据表定义（共 8 张表）。

question          题目主表（题库）
import_log        导入批次日志
import_log_item   导入明细：每条题目的导入结果（成功/重复/失败）
profile           本地档案：离线多用户，通过切换档案隔离作答数据
answer_log        作答流水：每次作答一条
answer_state      作答状态快照：错题次数、连对次数、最近结果（用于错题本/统计）
favorite          收藏夹
app_setting       键值配置（当前档案、去重阈值等运行时设置）
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base

# ------------------------------------------------------------------ 题型常量
TYPE_SINGLE = "single"      # 单选
TYPE_MULTIPLE = "multiple"  # 多选
TYPE_JUDGE = "judge"        # 判断
TYPE_SHORT = "short"        # 简答
QUESTION_TYPES = (TYPE_SINGLE, TYPE_MULTIPLE, TYPE_JUDGE, TYPE_SHORT)

# ------------------------------------------------------------------ 导入明细状态
ITEM_SUCCESS = "success"
ITEM_DUPLICATE = "duplicate"
ITEM_FAILED = "failed"


def _now() -> datetime:
    return datetime.now()


class Question(Base):
    """题目主表。options / answer 以 JSON 字符串存储，兼容各题型结构。"""

    __tablename__ = "question"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    ext_id: Mapped[Optional[str]] = mapped_column(String(128), index=True)  # 源 JSON 中的 id
    type: Mapped[str] = mapped_column(String(16), index=True, default=TYPE_SINGLE)
    title: Mapped[str] = mapped_column(Text)                                  # 题干（保留 LaTeX）
    options: Mapped[Optional[str]] = mapped_column(Text)                      # JSON: [{"key","text"}]
    answer: Mapped[str] = mapped_column(Text)                                 # JSON: "A" / ["A","B"] / true / "文本"
    analysis: Mapped[Optional[str]] = mapped_column(Text)                     # 解析
    stem_norm: Mapped[str] = mapped_column(Text, default="")                  # 归一化题干（去重比较）
    stem_hash: Mapped[str] = mapped_column(String(64), index=True, default="")  # md5(stem_norm)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=_now, onupdate=_now)

    __table_args__ = (Index("ix_question_type_hash", "type", "stem_hash"),)


class ImportLog(Base):
    """一次 JSON 导入的汇总日志。"""

    __tablename__ = "import_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    source_name: Mapped[str] = mapped_column(String(512), default="")   # 上传文件名 / 本地路径
    file_hash: Mapped[str] = mapped_column(String(64), default="")      # 文件内容 md5
    total: Mapped[int] = mapped_column(Integer, default=0)              # 文件内题目总数
    imported: Mapped[int] = mapped_column(Integer, default=0)           # 成功入库
    duplicated: Mapped[int] = mapped_column(Integer, default=0)         # 重复跳过
    failed: Mapped[int] = mapped_column(Integer, default=0)             # 解析失败
    threshold: Mapped[float] = mapped_column(Float, default=0.9)        # 本次使用的去重阈值
    status: Mapped[str] = mapped_column(String(16), default="success")  # success / partial / failed
    message: Mapped[Optional[str]] = mapped_column(Text)                # 概要说明
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now, index=True)

    items: Mapped[list["ImportLogItem"]] = relationship(
        back_populates="log",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )


class ImportLogItem(Base):
    """导入明细，供日志详情页逐条核对。"""

    __tablename__ = "import_log_item"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    log_id: Mapped[int] = mapped_column(
        ForeignKey("import_log.id", ondelete="CASCADE"), index=True
    )
    row_index: Mapped[int] = mapped_column(Integer, default=0)          # 在源文件中的序号（从 1 开始）
    status: Mapped[str] = mapped_column(String(16), index=True)         # success / duplicate / failed
    reason: Mapped[Optional[str]] = mapped_column(Text)                 # 重复来源 / 失败原因
    question_id: Mapped[Optional[int]] = mapped_column(Integer)          # 成功时入库的题目 id
    matched_question_id: Mapped[Optional[int]] = mapped_column(Integer)  # 重复时命中的已有题目 id
    similarity: Mapped[Optional[float]] = mapped_column(Float)           # 重复时的相似度
    title_preview: Mapped[Optional[str]] = mapped_column(String(255))    # 题干摘要

    log: Mapped["ImportLog"] = relationship(back_populates="items")


class Profile(Base):
    """本地档案：不登录，用「档案切换」实现多人数据隔离。"""

    __tablename__ = "profile"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(64), unique=True)
    is_default: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)


class AnswerLog(Base):
    """作答流水：一次作答一条记录，用于统计与回看。"""

    __tablename__ = "answer_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    profile_id: Mapped[int] = mapped_column(
        ForeignKey("profile.id", ondelete="CASCADE"), index=True
    )
    question_id: Mapped[int] = mapped_column(
        ForeignKey("question.id", ondelete="CASCADE"), index=True
    )
    user_answer: Mapped[Optional[str]] = mapped_column(Text)             # JSON：用户作答
    is_correct: Mapped[Optional[bool]] = mapped_column(Boolean)          # None=简答待自评
    mode: Mapped[str] = mapped_column(String(16), default="sequence")    # sequence/random/wrong
    duration_ms: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now, index=True)


class AnswerState(Base):
    """作答状态快照（每个档案 × 每道题一条）。"""

    __tablename__ = "answer_state"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    profile_id: Mapped[int] = mapped_column(
        ForeignKey("profile.id", ondelete="CASCADE"), index=True
    )
    question_id: Mapped[int] = mapped_column(
        ForeignKey("question.id", ondelete="CASCADE"), index=True
    )
    practice_count: Mapped[int] = mapped_column(Integer, default=0)      # 累计作答次数
    wrong_count: Mapped[int] = mapped_column(Integer, default=0)         # 累计答错次数
    correct_streak: Mapped[int] = mapped_column(Integer, default=0)      # 当前连对次数（错题移出依据）
    last_correct: Mapped[Optional[bool]] = mapped_column(Boolean)
    last_answer: Mapped[Optional[str]] = mapped_column(Text)             # JSON
    last_answered_at: Mapped[Optional[datetime]] = mapped_column(DateTime)

    __table_args__ = (UniqueConstraint("profile_id", "question_id", name="uq_state_profile_question"),)


class Favorite(Base):
    """收藏夹。"""

    __tablename__ = "favorite"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    profile_id: Mapped[int] = mapped_column(
        ForeignKey("profile.id", ondelete="CASCADE"), index=True
    )
    question_id: Mapped[int] = mapped_column(
        ForeignKey("question.id", ondelete="CASCADE"), index=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)

    __table_args__ = (UniqueConstraint("profile_id", "question_id", name="uq_fav_profile_question"),)


class AppSetting(Base):
    """键值配置表。"""

    __tablename__ = "app_setting"

    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    value: Mapped[Optional[str]] = mapped_column(Text)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=_now, onupdate=_now)
