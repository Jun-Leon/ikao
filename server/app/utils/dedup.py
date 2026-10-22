# -*- coding: utf-8 -*-
"""题干相似度去重。

两级策略：
1. 精确命中：md5(归一化题干) 相同 —— O(1)
2. 模糊命中：token_sort_ratio >= 阈值 —— 逐条比较，先用长度比预筛减少比较次数

优先使用 rapidfuzz；若环境缺少该库，自动退化为 difflib，保证功能可用。
"""

from __future__ import annotations

from typing import Dict, List, Optional, Tuple

try:  # pragma: no cover - 依赖存在与否决定分支
    from rapidfuzz import fuzz

    def _ratio(a: str, b: str) -> float:
        return fuzz.token_sort_ratio(a, b) / 100.0

    BACKEND = "rapidfuzz"
except ImportError:  # pragma: no cover
    from difflib import SequenceMatcher

    def _ratio(a: str, b: str) -> float:
        return SequenceMatcher(None, a, b).ratio()

    BACKEND = "difflib"


class DedupIndex:
    """内存去重索引：导入时先把已有题库装进索引，再逐条判断。"""

    def __init__(self, threshold: float = 0.90) -> None:
        self.threshold = max(0.0, min(1.0, threshold))
        self._exact: Dict[str, List[int]] = {}          # md5 -> [question_id]
        self._entries: List[Tuple[int, str]] = []       # [(question_id, stem_norm)]

    def add(self, question_id: int, stem_norm: str, stem_hash: str = "") -> None:
        """把一个已存在的题目加入索引。"""
        norm = stem_norm or ""
        if stem_hash:
            self._exact.setdefault(stem_hash, []).append(question_id)
        if norm:
            self._entries.append((question_id, norm))

    def find_duplicate(
        self, stem_norm: str, stem_hash: str = ""
    ) -> Optional[Tuple[int, float]]:
        """查找重复题目。

        返回 (命中的已有题目 id, 相似度)；未命中返回 None。
        精确命中相似度记为 1.0。
        """
        norm = stem_norm or ""
        if not norm:
            return None

        if stem_hash and stem_hash in self._exact:
            return self._exact[stem_hash][0], 1.0

        best_id: Optional[int] = None
        best_score = 0.0
        len_norm = len(norm)
        for qid, other in self._entries:
            # 长度预筛：长度相差过大不可能达到阈值
            longer = max(len_norm, len(other))
            if longer and min(len_norm, len(other)) / longer < self.threshold:
                continue
            score = _ratio(norm, other)
            if score > best_score:
                best_score = score
                best_id = qid
                if score >= 0.999:
                    break
        if best_id is not None and best_score >= self.threshold:
            return best_id, round(best_score, 4)
        return None

    def __len__(self) -> int:
        return len(self._entries)
