# -*- coding: utf-8 -*-
"""刷题核心服务：抽题、判分、作答状态维护、错题本与收藏。

设计要点：
- 判分放在服务端（题目答案不下发到前端），提交后随结果一起回传正确答案与解析。
- 每次作答写一条 ``AnswerLog``（流水，用于统计与回看），
  同时更新 ``AnswerState``（快照，用于错题本与进度展示）。
- 简答题没有客观答案：先记为「待自评」（is_correct=None），再由用户自评补齐。
- 所有读写都以 profile_id 为界，保证多档案数据互不干扰。
"""

from __future__ import annotations

import json
import re
from datetime import datetime
from typing import Any, Dict, List, Optional, Sequence, Tuple

from sqlalchemy import and_, case, func, or_, select
from sqlalchemy.orm import Session

from ..models import (
    TYPE_JUDGE,
    TYPE_MULTIPLE,
    TYPE_SHORT,
    TYPE_SINGLE,
    AnswerLog,
    AnswerState,
    Favorite,
    Question,
)

MODE_SEQUENCE = "sequence"
MODE_RANDOM = "random"
MODE_WRONG = "wrong"
MODE_FAVORITE = "favorite"
MODE_RECITE = "recite"
PRACTICE_MODES = (MODE_SEQUENCE, MODE_RANDOM, MODE_WRONG, MODE_FAVORITE, MODE_RECITE)

DEFAULT_BATCH = 20
MAX_BATCH = 200
MAX_PAGE_SIZE = 200

# 错题本 / 收藏夹排序
ORDER_RECENT = "recent"
ORDER_OLDEST = "oldest"
ORDER_WRONG = "wrong"
REVIEW_ORDERS = (ORDER_RECENT, ORDER_OLDEST, ORDER_WRONG)

_LETTER_RE = re.compile(r"[A-Za-z]")
_JUDGE_TRUE = {"true", "t", "1", "y", "yes", "正确", "对", "是", "√"}
_JUDGE_FALSE = {"false", "f", "0", "n", "no", "错误", "错", "否", "×", "x"}


class PracticeError(ValueError):
    """刷题相关的业务校验错误（路由层转成 400，附中文提示）。"""


# ------------------------------------------------------------------ 判分
def judge(question: Question, user_answer: Any) -> Optional[bool]:
    """判分；返回 None 表示该题无法自动判分（简单自评或题库缺答案）。

    题库里可能有缺答案的题（导入时容忍），这类题不能判成「错」，
    统一返回 None，让前端按「无参考答案」处理。
    """
    correct = _load_json(question.answer, None)

    if question.type == TYPE_JUDGE:
        if not isinstance(correct, bool):
            return None
        picked = _to_bool(user_answer)
        if picked is None:
            return None
        return picked == correct

    if question.type == TYPE_SINGLE:
        picked = _upper(user_answer)
        target = _upper(correct)
        if not picked or not target:
            return None
        return picked == target

    if question.type == TYPE_MULTIPLE:
        picked = _to_keys(user_answer)
        target = _to_keys(correct)
        if not picked or not target:
            return None
        return picked == target

    return None


def _upper(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip().upper()


def _to_keys(value: Any) -> List[str]:
    """把作答（"AB" / ["A","B"] / "A、B"）统一成排序去重后的字母列表。"""
    if value is None:
        return []
    if isinstance(value, (list, tuple, set)):
        letters: set = set()
        for item in value:
            letters.update(_to_keys(item))
        return sorted(letters)
    return sorted({ch.upper() for ch in _LETTER_RE.findall(str(value))})


def _to_bool(value: Any) -> Optional[bool]:
    if isinstance(value, bool):
        return value
    if value is None:
        return None
    text = str(value).strip().lower()
    if text in _JUDGE_TRUE:
        return True
    if text in _JUDGE_FALSE:
        return False
    return None


def _is_blank(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, (list, tuple, set)):
        return len(value) == 0
    return not str(value).strip()


def _dump(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False)


def _load_json(raw: Optional[str], default: Any) -> Any:
    if raw in (None, ""):
        return default
    try:
        return json.loads(raw)
    except (TypeError, ValueError):
        return default


# ------------------------------------------------------------------ 服务
class PracticeService:
    """刷题的读写操作，全部作用在「当前档案」上。"""

    def __init__(self, db: Session, profile_id: int) -> None:
        self.db = db
        self.profile_id = profile_id

    # ------------------------------------------------------------- 抽题
    def list_questions(
        self,
        mode: str = MODE_SEQUENCE,
        qtype: Optional[str] = None,
        keyword: Optional[str] = None,
        count: int = DEFAULT_BATCH,
        page: int = 1,
    ) -> Tuple[List[Question], int]:
        """按模式抽题，返回（题目列表，符合条件总数）。"""
        if mode not in PRACTICE_MODES:
            raise PracticeError(f"未知的练习模式：{mode}")

        count = max(1, min(int(count or DEFAULT_BATCH), MAX_BATCH))
        page = max(1, int(page or 1))

        stmt = select(Question)
        if qtype:
            stmt = stmt.where(Question.type == qtype)
        if keyword and keyword.strip():
            kw = keyword.strip()
            stmt = stmt.where(
                or_(
                    Question.title.contains(kw, autoescape=True),
                    Question.options.contains(kw, autoescape=True),
                )
            )

        if mode == MODE_WRONG:
            stmt = stmt.join(AnswerState, AnswerState.question_id == Question.id).where(
                AnswerState.profile_id == self.profile_id,
                AnswerState.last_correct.is_(False),
            )
            order_by = (AnswerState.last_answered_at.desc(), Question.id.asc())
        elif mode == MODE_FAVORITE:
            stmt = stmt.join(Favorite, Favorite.question_id == Question.id).where(
                Favorite.profile_id == self.profile_id,
            )
            order_by = (Favorite.created_at.desc(), Question.id.asc())
        elif mode == MODE_RANDOM:
            order_by = (func.random(),)
        elif mode == MODE_RECITE:
            # 背题：稳定按题号升序，配合分页一批批往后背，不会重复也不会漏
            order_by = (Question.id.asc(),)
        else:
            # 顺序：全库统一排队，未做过的题优先（按 id 升序）。
            # 这样每次「开始刷题」都会往后推进，不会一直卡在同一个来源的前几道题上。
            stmt = stmt.outerjoin(
                AnswerState,
                and_(
                    AnswerState.question_id == Question.id,
                    AnswerState.profile_id == self.profile_id,
                ),
            )
            order_by = (case((AnswerState.id.is_(None), 0), else_=1), Question.id.asc())

        total = int(
            self.db.scalar(select(func.count()).select_from(stmt.order_by(None).subquery())) or 0
        )
        rows = (
            self.db.execute(stmt.order_by(*order_by).offset((page - 1) * count).limit(count))
            .scalars()
            .all()
        )
        return list(rows), total

    def decorate(self, rows: Sequence[Question], with_answer: bool = False) -> List[Dict[str, Any]]:
        """批量补上作答次数、错题次数与收藏状态（避免 N+1 查询）。

        with_answer=True 时额外下发 answer / analysis，仅供「背题模式」使用；
        其余模式不下发，保证判分仍在服务端完成。
        """
        ids = [row.id for row in rows]
        states: Dict[int, AnswerState] = {}
        favorites: set = set()
        if ids:
            states = {
                state.question_id: state
                for state in self.db.execute(
                    select(AnswerState).where(
                        AnswerState.profile_id == self.profile_id,
                        AnswerState.question_id.in_(ids),
                    )
                )
                .scalars()
                .all()
            }
            favorites = set(
                self.db.execute(
                    select(Favorite.question_id).where(
                        Favorite.profile_id == self.profile_id,
                        Favorite.question_id.in_(ids),
                    )
                )
                .scalars()
                .all()
            )

        items: List[Dict[str, Any]] = []
        for row in rows:
            state = states.get(row.id)
            item: Dict[str, Any] = {
                "id": row.id,
                "ext_id": row.ext_id,
                "type": row.type,
                "title": row.title,
                "options": _load_json(row.options, []),
                "practice_count": state.practice_count if state else 0,
                "wrong_count": state.wrong_count if state else 0,
                "is_favorite": row.id in favorites,
            }
            if with_answer:
                item["answer"] = _load_json(row.answer, None)
                item["analysis"] = row.analysis
            items.append(item)
        return items

    # ------------------------------------------------------------- 作答
    def submit(
        self,
        question_id: int,
        user_answer: Any,
        mode: str = MODE_SEQUENCE,
        duration_ms: int = 0,
    ) -> Dict[str, Any]:
        """提交一题作答：写流水 + 更新快照，返回判分结果。"""
        question = self.db.get(Question, question_id)
        if question is None:
            raise PracticeError("题目不存在")
        if question.type != TYPE_SHORT and _is_blank(user_answer):
            raise PracticeError("请先作答再提交")

        is_correct = judge(question, user_answer)

        self.db.add(
            AnswerLog(
                profile_id=self.profile_id,
                question_id=question_id,
                user_answer=_dump(user_answer),
                is_correct=is_correct,
                mode=mode if mode in PRACTICE_MODES else MODE_SEQUENCE,
                duration_ms=max(0, int(duration_ms or 0)),
            )
        )
        self._apply_state(question_id, user_answer, is_correct)
        self.db.commit()

        return {
            "question_id": question_id,
            "is_correct": is_correct,
            "correct_answer": _load_json(question.answer, None),
            "analysis": question.analysis,
            "need_self_eval": question.type == TYPE_SHORT,
            "state": self.state_dict(question_id),
        }

    def self_evaluate(
        self, question_id: int, is_correct: bool, mode: str = MODE_SEQUENCE
    ) -> Dict[str, Any]:
        """简答题自评：补齐最近一条待自评流水的 is_correct，并更新快照。"""
        question = self.db.get(Question, question_id)
        if question is None:
            raise PracticeError("题目不存在")
        if question.type != TYPE_SHORT:
            raise PracticeError("只有简答题需要自评")

        log = self.db.scalar(
            select(AnswerLog)
            .where(
                AnswerLog.profile_id == self.profile_id,
                AnswerLog.question_id == question_id,
            )
            .order_by(AnswerLog.id.desc())
            .limit(1)
        )
        if log is not None and log.is_correct is None:
            log.is_correct = bool(is_correct)

        state = self._get_state(question_id, create=True)
        if is_correct:
            state.correct_streak += 1
        else:
            state.wrong_count += 1
            state.correct_streak = 0
        state.last_correct = bool(is_correct)
        self.db.commit()

        return {
            "question_id": question_id,
            "is_correct": bool(is_correct),
            "correct_answer": _load_json(question.answer, None),
            "analysis": question.analysis,
            "need_self_eval": False,
            "state": self.state_dict(question_id),
        }

    # ------------------------------------------------------------- 错题 / 收藏
    def list_wrong(
        self,
        page: int = 1,
        page_size: int = 20,
        qtype: Optional[str] = None,
        keyword: Optional[str] = None,
        order: str = ORDER_RECENT,
    ) -> Tuple[List[Dict[str, Any]], int]:
        """错题本分页（最近一次作答为错的题），带答案与解析。"""
        stmt = (
            select(Question, AnswerState)
            .join(AnswerState, AnswerState.question_id == Question.id)
            .where(
                AnswerState.profile_id == self.profile_id,
                AnswerState.last_correct.is_(False),
            )
        )
        stmt = self._apply_filters(stmt, qtype, keyword)
        total = self._count_of(stmt)

        if order == ORDER_WRONG:
            order_by = (AnswerState.wrong_count.desc(), AnswerState.last_answered_at.desc())
        elif order == ORDER_OLDEST:
            order_by = (AnswerState.last_answered_at.asc(), Question.id.asc())
        else:
            order_by = (AnswerState.last_answered_at.desc(), Question.id.asc())

        rows = (
            self.db.execute(self._paginate(stmt.order_by(*order_by), page, page_size)).all()
        )
        items = [
            self._review_item(question, state, marked_at=state.last_answered_at)
            for question, state in rows
        ]
        return items, total

    def list_favorites(
        self,
        page: int = 1,
        page_size: int = 20,
        qtype: Optional[str] = None,
        keyword: Optional[str] = None,
        order: str = ORDER_RECENT,
    ) -> Tuple[List[Dict[str, Any]], int]:
        """收藏夹分页，带答案与解析；顺带带上该题的作答状态。"""
        stmt = (
            select(Question, Favorite, AnswerState)
            .join(Favorite, Favorite.question_id == Question.id)
            .outerjoin(
                AnswerState,
                and_(
                    AnswerState.question_id == Question.id,
                    AnswerState.profile_id == self.profile_id,
                ),
            )
            .where(Favorite.profile_id == self.profile_id)
        )
        stmt = self._apply_filters(stmt, qtype, keyword)
        total = self._count_of(stmt)

        if order == ORDER_OLDEST:
            order_by = (Favorite.created_at.asc(), Question.id.asc())
        else:
            order_by = (Favorite.created_at.desc(), Question.id.asc())

        rows = (
            self.db.execute(self._paginate(stmt.order_by(*order_by), page, page_size)).all()
        )
        items = [
            self._review_item(question, state, marked_at=favorite.created_at, is_favorite=True)
            for question, favorite, state in rows
        ]
        return items, total

    # ------------------------------------------------------------- 状态
    def state_dict(self, question_id: int) -> Dict[str, Any]:
        state = self.db.scalar(
            select(AnswerState).where(
                AnswerState.profile_id == self.profile_id,
                AnswerState.question_id == question_id,
            )
        )
        if state is None:
            return {
                "practice_count": 0,
                "wrong_count": 0,
                "correct_streak": 0,
                "last_correct": None,
                "is_favorite": self.is_favorite(question_id),
            }
        return {
            "practice_count": state.practice_count,
            "wrong_count": state.wrong_count,
            "correct_streak": state.correct_streak,
            "last_correct": state.last_correct,
            "is_favorite": self.is_favorite(question_id),
        }

    def is_favorite(self, question_id: int) -> bool:
        return (
            self.db.scalar(
                select(Favorite.id).where(
                    Favorite.profile_id == self.profile_id,
                    Favorite.question_id == question_id,
                )
            )
            is not None
        )

    def toggle_favorite(self, question_id: int) -> bool:
        """收藏 / 取消收藏，返回操作后的收藏状态。"""
        if self.db.get(Question, question_id) is None:
            raise PracticeError("题目不存在")

        row = self.db.scalar(
            select(Favorite).where(
                Favorite.profile_id == self.profile_id,
                Favorite.question_id == question_id,
            )
        )
        if row is None:
            self.db.add(Favorite(profile_id=self.profile_id, question_id=question_id))
            self.db.commit()
            return True

        self.db.delete(row)
        self.db.commit()
        return False

    def remove_wrong(self, question_id: int) -> bool:
        """把题目移出错题本（视为已掌握：清空错误次数并标记最近一次为正确）。"""
        state = self.db.scalar(
            select(AnswerState).where(
                AnswerState.profile_id == self.profile_id,
                AnswerState.question_id == question_id,
            )
        )
        if state is None or state.last_correct is not False:
            return False
        state.last_correct = True
        state.wrong_count = 0
        state.correct_streak = max(1, state.correct_streak)
        self.db.commit()
        return True

    def stats(self) -> Dict[str, int]:
        """当前档案的刷题概览。"""
        answered = int(
            self.db.scalar(
                select(func.count(AnswerState.id)).where(
                    AnswerState.profile_id == self.profile_id,
                    AnswerState.practice_count > 0,
                )
            )
            or 0
        )
        correct = int(
            self.db.scalar(
                select(func.count(AnswerState.id)).where(
                    AnswerState.profile_id == self.profile_id,
                    AnswerState.last_correct.is_(True),
                )
            )
            or 0
        )
        wrong = int(
            self.db.scalar(
                select(func.count(AnswerState.id)).where(
                    AnswerState.profile_id == self.profile_id,
                    AnswerState.last_correct.is_(False),
                )
            )
            or 0
        )
        favorite = int(
            self.db.scalar(
                select(func.count(Favorite.id)).where(Favorite.profile_id == self.profile_id)
            )
            or 0
        )
        total = int(self.db.scalar(select(func.count(Question.id))) or 0)
        return {
            "total": total,
            "answered": answered,
            "correct": correct,
            "wrong": wrong,
            "favorite": favorite,
        }

    # ------------------------------------------------------------- 内部
    def _get_state(self, question_id: int, create: bool = False) -> Optional[AnswerState]:
        state = self.db.scalar(
            select(AnswerState).where(
                AnswerState.profile_id == self.profile_id,
                AnswerState.question_id == question_id,
            )
        )
        if state is None and create:
            state = AnswerState(profile_id=self.profile_id, question_id=question_id)
            self.db.add(state)
            self.db.flush()
        return state

    def _apply_state(self, question_id: int, last_answer: Any, is_correct: Optional[bool]) -> None:
        """更新作答快照；is_correct 为 None（简答待自评）时不动对错相关字段。"""
        state = self._get_state(question_id, create=True)
        state.practice_count += 1
        state.last_answer = _dump(last_answer)
        state.last_answered_at = datetime.now()

        if is_correct is True:
            state.correct_streak += 1
            state.last_correct = True
        elif is_correct is False:
            state.wrong_count += 1
            state.correct_streak = 0
            state.last_correct = False

    # ------------------------------------------------------------- 通用
    @staticmethod
    def _apply_filters(stmt, qtype, keyword):
        if qtype:
            stmt = stmt.where(Question.type == qtype)
        if keyword and keyword.strip():
            kw = keyword.strip()
            stmt = stmt.where(
                or_(
                    Question.title.contains(kw, autoescape=True),
                    Question.options.contains(kw, autoescape=True),
                )
            )
        return stmt

    def _count_of(self, stmt) -> int:
        return int(
            self.db.scalar(select(func.count()).select_from(stmt.order_by(None).subquery())) or 0
        )

    @staticmethod
    def _paginate(stmt, page: int, page_size: int):
        page = max(1, int(page or 1))
        page_size = max(1, min(int(page_size or DEFAULT_BATCH), MAX_PAGE_SIZE))
        return stmt.offset((page - 1) * page_size).limit(page_size)

    @staticmethod
    def _review_item(
        question: Question,
        state: Optional[AnswerState],
        marked_at: Optional[datetime] = None,
        is_favorite: Optional[bool] = None,
    ) -> Dict[str, Any]:
        """错题本 / 收藏夹统一的行结构（含答案与解析）。"""
        return {
            "id": question.id,
            "ext_id": question.ext_id,
            "type": question.type,
            "title": question.title,
            "options": _load_json(question.options, []),
            "answer": _load_json(question.answer, None),
            "analysis": question.analysis,
            "practice_count": state.practice_count if state else 0,
            "wrong_count": state.wrong_count if state else 0,
            "correct_streak": state.correct_streak if state else 0,
            "last_correct": state.last_correct if state else None,
            "last_answer": _load_json(state.last_answer, None) if state else None,
            "last_answered_at": state.last_answered_at if state else None,
            "marked_at": marked_at,
            "is_favorite": is_favorite if is_favorite is not None else True,
        }
