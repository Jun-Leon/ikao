# -*- coding: utf-8 -*-
"""刷题统计看板服务：概览、题型/来源/模式分布、练习趋势、高频错题。

统计口径说明：
- 「已作答」= answer_state 里 practice_count>0 的不同题目数；
- 「答对 / 答错」= answer_state 里最近一次作答结果（错题本同口径）；
- 「正确率」= answer_log 流水中已判分记录的答对占比（含重复作答，更能反映实际手感）；
- 简答题未自评的流水 is_correct 为 NULL，不计入正确率分母。
"""

from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional

from sqlalchemy import case, func, select
from sqlalchemy.orm import Session

from ..models import (
    QUESTION_TYPES,
    TYPE_JUDGE,
    TYPE_MULTIPLE,
    TYPE_SHORT,
    TYPE_SINGLE,
    AnswerLog,
    AnswerState,
    Favorite,
    Question,
)

TREND_DAYS = 14
TOP_WRONG_LIMIT = 10

TYPE_LABELS = {
    TYPE_SINGLE: "单选题",
    TYPE_MULTIPLE: "多选题",
    TYPE_JUDGE: "判断题",
    TYPE_SHORT: "简答题",
}

MODE_LABELS = {
    "sequence": "顺序练习",
    "random": "随机练习",
    "wrong": "错题重做",
    "favorite": "收藏练习",
    "recite": "背题模式",
}

_CORRECT_SUM = func.sum(case((AnswerLog.is_correct.is_(True), 1), else_=0))
_SCORED_SUM = func.sum(case((AnswerLog.is_correct.is_not(None), 1), else_=0))


def _rate(correct: int, scored: int) -> Optional[float]:
    if not scored:
        return None
    return round(correct / scored, 4)


class StatsService:
    """按档案聚合刷题数据，供统计看板使用。"""

    def __init__(self, db: Session, profile_id: int) -> None:
        self.db = db
        self.profile_id = profile_id

    # ------------------------------------------------------------- 看板
    def board(self, trend_days: int = TREND_DAYS) -> Dict[str, Any]:
        trend_days = max(7, min(int(trend_days or TREND_DAYS), 90))
        return {
            "overview": self.overview(),
            "by_type": self.by_type(),
            "by_mode": self.by_mode(),
            "trend": self.trend(trend_days),
            "top_wrong": self.top_wrong(),
        }

    def overview(self) -> Dict[str, Any]:
        total_questions = int(self.db.scalar(select(func.count(Question.id))) or 0)
        answered = self._count_states(AnswerState.practice_count > 0)
        correct = self._count_states(AnswerState.last_correct.is_(True))
        wrong = self._count_states(AnswerState.last_correct.is_(False))
        favorite = int(
            self.db.scalar(
                select(func.count(Favorite.id)).where(Favorite.profile_id == self.profile_id)
            )
            or 0
        )

        attempts = int(
            self.db.scalar(
                select(func.count(AnswerLog.id)).where(AnswerLog.profile_id == self.profile_id)
            )
            or 0
        )
        scored = int(
            self.db.scalar(
                select(func.count(AnswerLog.id)).where(
                    AnswerLog.profile_id == self.profile_id,
                    AnswerLog.is_correct.is_not(None),
                )
            )
            or 0
        )
        scored_correct = int(
            self.db.scalar(
                select(func.count(AnswerLog.id)).where(
                    AnswerLog.profile_id == self.profile_id,
                    AnswerLog.is_correct.is_(True),
                )
            )
            or 0
        )
        duration_ms = int(
            self.db.scalar(
                select(func.coalesce(func.sum(AnswerLog.duration_ms), 0)).where(
                    AnswerLog.profile_id == self.profile_id
                )
            )
            or 0
        )

        days = self._study_dates()
        return {
            "total_questions": total_questions,
            "answered": answered,
            "correct": correct,
            "wrong": wrong,
            "unanswered": max(0, total_questions - answered),
            "favorite": favorite,
            "accuracy": _rate(scored_correct, scored),
            "attempts": attempts,
            "scored": scored,
            "study_days": len(days),
            "streak_days": self._streak_days(days),
            "duration_ms": duration_ms,
        }

    def by_type(self) -> List[Dict[str, Any]]:
        totals = dict(
            self.db.execute(select(Question.type, func.count(Question.id)).group_by(Question.type)).all()
        )

        answered = dict(
            self.db.execute(
                select(Question.type, func.count(AnswerState.id))
                .join(AnswerState, AnswerState.question_id == Question.id)
                .where(
                    AnswerState.profile_id == self.profile_id,
                    AnswerState.practice_count > 0,
                )
                .group_by(Question.type)
            ).all()
        )
        wrong = dict(
            self.db.execute(
                select(Question.type, func.count(AnswerState.id))
                .join(AnswerState, AnswerState.question_id == Question.id)
                .where(
                    AnswerState.profile_id == self.profile_id,
                    AnswerState.last_correct.is_(False),
                )
                .group_by(Question.type)
            ).all()
        )
        attempts: Dict[str, int] = {}
        correct: Dict[str, int] = {}
        scored: Dict[str, int] = {}
        for qtype, total, right, settled in self.db.execute(
            select(
                Question.type,
                func.count(AnswerLog.id),
                _CORRECT_SUM,
                _SCORED_SUM,
            )
            .join(AnswerLog, AnswerLog.question_id == Question.id)
            .where(AnswerLog.profile_id == self.profile_id)
            .group_by(Question.type)
        ).all():
            attempts[qtype] = int(total or 0)
            correct[qtype] = int(right or 0)
            scored[qtype] = int(settled or 0)

        items: List[Dict[str, Any]] = []
        for qtype in QUESTION_TYPES:
            items.append(
                {
                    "type": qtype,
                    "label": TYPE_LABELS.get(qtype, qtype),
                    "total": int(totals.get(qtype, 0)),
                    "answered": int(answered.get(qtype, 0)),
                    "wrong": int(wrong.get(qtype, 0)),
                    "attempts": attempts.get(qtype, 0),
                    "correct": correct.get(qtype, 0),
                    "scored": scored.get(qtype, 0),
                    "accuracy": _rate(correct.get(qtype, 0), scored.get(qtype, 0)),
                }
            )
        return items

    def by_mode(self) -> List[Dict[str, Any]]:
        items: List[Dict[str, Any]] = []
        for mode, count in self.db.execute(
            select(AnswerLog.mode, func.count(AnswerLog.id))
            .where(AnswerLog.profile_id == self.profile_id)
            .group_by(AnswerLog.mode)
            .order_by(func.count(AnswerLog.id).desc())
        ).all():
            items.append(
                {
                    "mode": mode or "sequence",
                    "label": MODE_LABELS.get(mode or "sequence", mode or "sequence"),
                    "attempts": int(count or 0),
                }
            )
        return items

    def trend(self, days: int = TREND_DAYS) -> List[Dict[str, Any]]:
        today = date.today()
        start = today - timedelta(days=days - 1)
        bucket: Dict[str, Dict[str, int]] = {}
        for day, total, right, settled in self.db.execute(
            select(
                func.date(AnswerLog.created_at),
                func.count(AnswerLog.id),
                _CORRECT_SUM,
                _SCORED_SUM,
            )
            .where(
                AnswerLog.profile_id == self.profile_id,
                AnswerLog.created_at >= datetime.combine(start, datetime.min.time()),
            )
            .group_by(func.date(AnswerLog.created_at))
        ).all():
            bucket[str(day)] = {
                "attempts": int(total or 0),
                "correct": int(right or 0),
                "scored": int(settled or 0),
            }

        items: List[Dict[str, Any]] = []
        for offset in range(days):
            current = start + timedelta(days=offset)
            key = current.strftime("%Y-%m-%d")
            data = bucket.get(key, {"attempts": 0, "correct": 0, "scored": 0})
            items.append(
                {
                    "date": key,
                    "attempts": data["attempts"],
                    "correct": data["correct"],
                    "accuracy": _rate(data["correct"], data["scored"]),
                }
            )
        return items

    def top_wrong(self) -> List[Dict[str, Any]]:
        items: List[Dict[str, Any]] = []
        for question_id, qtype, title, wrong_count, last_correct in self.db.execute(
            select(
                Question.id,
                Question.type,
                Question.title,
                AnswerState.wrong_count,
                AnswerState.last_correct,
            )
            .join(AnswerState, AnswerState.question_id == Question.id)
            .where(
                AnswerState.profile_id == self.profile_id,
                AnswerState.wrong_count > 0,
            )
            .order_by(AnswerState.wrong_count.desc(), AnswerState.last_answered_at.desc())
            .limit(TOP_WRONG_LIMIT)
        ).all():
            items.append(
                {
                    "question_id": question_id,
                    "type": qtype,
                    "title": title or "",
                    "wrong_count": int(wrong_count or 0),
                    "last_correct": last_correct,
                }
            )
        return items

    # ------------------------------------------------------------- 内部
    def _count_states(self, *conditions) -> int:
        return int(
            self.db.scalar(
                select(func.count(AnswerState.id)).where(
                    AnswerState.profile_id == self.profile_id, *conditions
                )
            )
            or 0
        )

    def _study_dates(self) -> List[date]:
        raw = self.db.execute(
            select(func.date(AnswerLog.created_at))
            .where(AnswerLog.profile_id == self.profile_id)
            .distinct()
        ).scalars().all()

        days: List[date] = []
        for item in raw:
            try:
                days.append(datetime.strptime(str(item), "%Y-%m-%d").date())
            except ValueError:
                continue
        return sorted(set(days), reverse=True)

    @staticmethod
    def _streak_days(days: List[date]) -> int:
        """最近连续练习天数：今天或昨天有记录才算连续。"""
        if not days:
            return 0
        today = date.today()
        if days[0] not in (today, today - timedelta(days=1)):
            return 0

        streak = 1
        for earlier, later in zip(days[1:], days[:-1]):
            if (later - earlier).days == 1:
                streak += 1
            else:
                break
        return streak
