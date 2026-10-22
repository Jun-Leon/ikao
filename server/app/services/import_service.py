# -*- coding: utf-8 -*-
"""题库导入服务。

流程：解析来源（JSON / CSV / Excel）-> 逐题归一化 -> 相似度去重 -> 入库
-> 写导入日志（含逐条明细）。整个过程只提交一次事务，避免半成品数据。
"""

from __future__ import annotations

import json
from typing import List, Optional, Tuple

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..config import settings
from ..models import (
    ITEM_DUPLICATE,
    ITEM_FAILED,
    ITEM_SUCCESS,
    ImportLog,
    ImportLogItem,
    Question,
)
from ..utils.dedup import BACKEND, DedupIndex
from ..utils.json_loader import (
    NormalizedQuestion,
    QuestionFormatError,
    normalize_question,
    parse_question_bank,
)
from ..utils.text_norm import md5_hash


class ImportService:
    """执行一次完整导入。"""

    def __init__(self, db: Session) -> None:
        self.db = db

    # ------------------------------------------------------------- 对外入口
    def import_text(
        self,
        raw_text: str,
        source_name: str = "uploaded.json",
        threshold: Optional[float] = None,
    ) -> ImportLog:
        """从 JSON 文本导入题库，返回导入日志。"""
        threshold = self._normalize_threshold(threshold)

        try:
            raw_items = parse_question_bank(raw_text)
        except QuestionFormatError as exc:
            return self._fail_log(source_name, md5_hash(raw_text), threshold, str(exc))

        return self._ingest(raw_items, source_name, md5_hash(raw_text), threshold)

    def import_items(
        self,
        raw_items: List[dict],
        source_name: str = "uploaded.table",
        threshold: Optional[float] = None,
        file_hash: str = "",
    ) -> ImportLog:
        """从「已解析成原始题目字典列表」的来源导入（CSV / Excel 走这里）。"""
        return self._ingest(
            raw_items,
            source_name,
            file_hash or md5_hash(f"{source_name}:{len(raw_items)}"),
            self._normalize_threshold(threshold),
        )

    # ------------------------------------------------------------- 内部主流程
    def _ingest(
        self,
        raw_items: List[dict],
        source_name: str,
        file_hash: str,
        threshold: float,
    ) -> ImportLog:
        log = ImportLog(source_name=source_name, file_hash=file_hash, threshold=threshold)
        log.total = len(raw_items)

        if len(raw_items) > settings.max_import_questions:
            log.status = "failed"
            log.message = (
                f"题目数量 {len(raw_items)} 超过上限 {settings.max_import_questions}，已中止导入"
            )
            return self._save_log(log)

        # 装载已有题库到去重索引
        index = self._build_index()

        items: List[ImportLogItem] = []
        imported = duplicated = failed = 0

        for offset, raw in enumerate(raw_items):
            row_index = offset + 1
            try:
                question = normalize_question(raw, row_index=row_index)
            except QuestionFormatError as exc:
                failed += 1
                items.append(
                    ImportLogItem(
                        row_index=row_index,
                        status=ITEM_FAILED,
                        reason=str(exc),
                    )
                )
                continue

            matched = index.find_duplicate(question.stem_norm, question.stem_hash)
            if matched is not None:
                matched_id, score = matched
                duplicated += 1
                items.append(
                    ImportLogItem(
                        row_index=row_index,
                        status=ITEM_DUPLICATE,
                        reason=f"与已有题目 id={matched_id} 相似度 {score:.3f}，判定为重复",
                        matched_question_id=matched_id,
                        similarity=score,
                        title_preview=question.preview,
                    )
                )
                continue

            row = self._to_row(question)
            self.db.add(row)
            self.db.flush()  # 立刻拿到自增 id
            imported += 1
            index.add(row.id, question.stem_norm, question.stem_hash)
            items.append(
                ImportLogItem(
                    row_index=row_index,
                    status=ITEM_SUCCESS,
                    question_id=row.id,
                    title_preview=question.preview,
                )
            )

        # 汇总
        log.imported = imported
        log.duplicated = duplicated
        log.failed = failed
        log.status = "success" if failed == 0 else ("partial" if imported else "failed")
        log.message = (
            f"解析 {log.total} 条：入库 {imported}，重复 {duplicated}，失败 {failed}"
            f"（去重阈值 {threshold}，算法 {BACKEND}）"
        )
        self.db.add(log)
        self.db.flush()

        for item in items:
            item.log_id = log.id
            self.db.add(item)

        self.db.commit()
        self.db.refresh(log)
        return log

    # ------------------------------------------------------------- 内部方法
    @staticmethod
    def _normalize_threshold(threshold: Optional[float]) -> float:
        value = settings.dedup_threshold if threshold is None else threshold
        return max(0.0, min(1.0, value))

    def _fail_log(
        self, source_name: str, file_hash: str, threshold: float, message: str
    ) -> ImportLog:
        log = ImportLog(source_name=source_name, file_hash=file_hash, threshold=threshold)
        log.total = 0
        log.status = "failed"
        log.message = message
        return self._save_log(log)

    def _save_log(self, log: ImportLog) -> ImportLog:
        self.db.add(log)
        self.db.commit()
        self.db.refresh(log)
        return log

    def _build_index(self) -> DedupIndex:
        index = DedupIndex(settings.dedup_threshold)
        rows = self.db.execute(select(Question.id, Question.stem_norm, Question.stem_hash)).all()
        for qid, stem_norm, stem_hash in rows:
            index.add(qid, stem_norm or "", stem_hash or "")
        return index

    @staticmethod
    def _to_row(question: NormalizedQuestion) -> Question:
        return Question(
            ext_id=question.ext_id or None,
            type=question.type,
            title=question.title,
            options=json.dumps(question.options, ensure_ascii=False) if question.options else None,
            answer=json.dumps(question.answer, ensure_ascii=False),
            analysis=question.analysis or None,
            stem_norm=question.stem_norm,
            stem_hash=question.stem_hash,
        )


# ------------------------------------------------------------------ 查询辅助
def count_questions(db: Session) -> int:
    return int(db.scalar(select(func.count(Question.id))) or 0)


def get_log_detail(db: Session, log_id: int) -> Optional[Tuple[ImportLog, int]]:
    log = db.get(ImportLog, log_id)
    if log is None:
        return None
    total = int(
        db.scalar(select(func.count(ImportLogItem.id)).where(ImportLogItem.log_id == log_id)) or 0
    )
    return log, total
