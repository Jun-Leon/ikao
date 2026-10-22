# -*- coding: utf-8 -*-
"""题库 JSON 解析（宽进严出）。

「宽进」：兼容常见的题库 JSON 写法，字段名、题型名、选项结构、答案写法都尽量容错。
「严出」：统一产出 :class:`NormalizedQuestion`，字段结构固定，后续入库不再做兼容判断。

支持的顶层结构::

    [ {...}, {...} ]                                  # 纯数组
    { "questions": [ ... ] }                          # 推荐结构
    { "data": [...] } / { "list": [...] } / { "items": [...] }

单题结构（字段名支持中英文别名）::

    {
      "id": "q1",
      "type": "single",                 # single/multiple/judge/short 或 单选/多选/判断/简答
      "title": "题干，支持 $LaTeX$",
      "options": ["A. 选项一", "B. 选项二"],   # 也支持 {"A": "选项一"} / [{"key":"A","text":"..."}]
      "answer": "A",                    # 多选用 ["A","B"]；判断用 true/false
      "analysis": "解析"
    }
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from ..models import QUESTION_TYPES, TYPE_JUDGE, TYPE_MULTIPLE, TYPE_SHORT, TYPE_SINGLE
from .text_norm import md5_hash, make_preview, normalize_stem, normalize_text

# ------------------------------------------------------------------ 字段别名
_TITLE_KEYS = ("title", "stem", "question", "content", "name", "题干", "题目", "问题")
_TYPE_KEYS = ("type", "kind", "qtype", "题型", "类型")
_OPTION_KEYS = ("options", "choices", "option", "选项")
_ANSWER_KEYS = ("answer", "answers", "correct", "correct_answer", "right_answer", "答案", "正确答案", "参考答案")
_ANALYSIS_KEYS = ("analysis", "explanation", "analyze", "explain", "解析", "分析", "说明")
_ID_KEYS = ("id", "qid", "code", "编号", "题号")

# 题型别名
_TYPE_ALIASES = {
    "single": TYPE_SINGLE, "singlechoice": TYPE_SINGLE, "radio": TYPE_SINGLE,
    "choice": TYPE_SINGLE, "sc": TYPE_SINGLE, "one": TYPE_SINGLE,
    "单选": TYPE_SINGLE, "单选题": TYPE_SINGLE, "单项选择题": TYPE_SINGLE,
    "单选题型": TYPE_SINGLE, "单选题(单选)": TYPE_SINGLE,
    "multiple": TYPE_MULTIPLE, "multichoice": TYPE_MULTIPLE, "multi": TYPE_MULTIPLE,
    "checkbox": TYPE_MULTIPLE, "mc": TYPE_MULTIPLE, "mcq": TYPE_MULTIPLE,
    "多选": TYPE_MULTIPLE, "多选题": TYPE_MULTIPLE, "多项选择题": TYPE_MULTIPLE, "多项选择": TYPE_MULTIPLE,
    "judge": TYPE_JUDGE, "truefalse": TYPE_JUDGE, "boolean": TYPE_JUDGE,
    "bool": TYPE_JUDGE, "tf": TYPE_JUDGE, "pd": TYPE_JUDGE,
    "判断": TYPE_JUDGE, "判断题": TYPE_JUDGE, "对错题": TYPE_JUDGE, "正误题": TYPE_JUDGE,
    "short": TYPE_SHORT, "essay": TYPE_SHORT, "subjective": TYPE_SHORT,
    "text": TYPE_SHORT, "blank": TYPE_SHORT, "fill": TYPE_SHORT, "qa": TYPE_SHORT,
    "简答": TYPE_SHORT, "简答题": TYPE_SHORT, "问答": TYPE_SHORT, "问答题": TYPE_SHORT,
    "填空": TYPE_SHORT, "填空题": TYPE_SHORT, "主观题": TYPE_SHORT,
}

_KEY_RE = re.compile(r"^\s*[（(\[]?([A-Za-z])[)）\].、:：]?\s*$")
_OPTION_PREFIX_RE = re.compile(r"^\s*[（(\[]?([A-Za-z])[)）\].、:：、]\s*")
_ANY_KEY_RE = re.compile(r"[A-Za-z]")
# 去掉「答案：」「正确答案是」这类前缀噪音
_ANSWER_NOISE_RE = re.compile(
    r"^\s*(?:答案|正确答案|参考答案|answer|ans)\s*[:：]?\s*(?:是|为)?\s*", re.IGNORECASE
)
# 纯选项字母写法（A、AC、A,C、A C……），避免把 "Beijing" 误抽成选项 B
_PURE_KEYS_RE = re.compile(r"^[A-Za-z\s,，、;；/|]+$")
_TRUE_WORDS = {"true", "t", "对", "正确", "是", "√", "yes", "y", "1"}
_FALSE_WORDS = {"false", "f", "错", "错误", "否", "×", "x", "no", "n", "0"}


@dataclass
class NormalizedQuestion:
    """归一化后的题目。"""

    type: str
    title: str
    options: List[Dict[str, str]] = field(default_factory=list)
    answer: Any = None
    analysis: str = ""
    ext_id: str = ""
    stem_norm: str = ""
    stem_hash: str = ""
    row_index: int = 0

    def finalize(self) -> "NormalizedQuestion":
        """补齐派生字段。"""
        self.stem_norm = normalize_stem(self.title)
        self.stem_hash = md5_hash(self.stem_norm)
        return self

    @property
    def preview(self) -> str:
        return make_preview(self.title)


class QuestionFormatError(ValueError):
    """单条题目格式错误（会被记入导入日志的 failed 明细）。"""


def parse_question_bank(raw_text: str) -> List[Dict[str, Any]]:
    """把 JSON 文本解析成「原始题目字典列表」。

    :raises QuestionFormatError: JSON 非法或顶层结构无法识别
    """
    try:
        data = json.loads(raw_text)
    except ValueError as exc:
        raise QuestionFormatError(f"JSON 语法错误：{exc}") from exc

    if isinstance(data, dict):
        for key in ("questions", "data", "list", "items", "questionList", "records"):
            value = data.get(key)
            if isinstance(value, list):
                return [item for item in value if isinstance(item, dict)]
        # 单个题目对象
        if _pick(data, _TITLE_KEYS) is not None:
            return [data]
        raise QuestionFormatError("未找到题目数组，请使用 questions / data / list 字段")

    if isinstance(data, list):
        items = [item for item in data if isinstance(item, dict)]
        if not items:
            raise QuestionFormatError("题目数组为空")
        return items

    raise QuestionFormatError("顶层结构必须是对象或数组")


def normalize_question(raw: Dict[str, Any], row_index: int = 0) -> NormalizedQuestion:
    """把单条原始字典归一化。"""
    title = _as_text(_pick(raw, _TITLE_KEYS))
    if not title.strip():
        raise QuestionFormatError("缺少题干（title/stem/题干）")

    options = _norm_options(_pick(raw, _OPTION_KEYS))
    qtype = _norm_type(_as_text(_pick(raw, _TYPE_KEYS)), options, _pick(raw, _ANSWER_KEYS))
    answer = _norm_answer(_pick(raw, _ANSWER_KEYS), qtype, options)
    analysis = _as_text(_pick(raw, _ANALYSIS_KEYS))
    ext_id = _as_text(_pick(raw, _ID_KEYS))

    return NormalizedQuestion(
        type=qtype,
        title=title.strip(),
        options=options,
        answer=answer,
        analysis=analysis.strip(),
        ext_id=ext_id.strip(),
        row_index=row_index,
    ).finalize()


# ------------------------------------------------------------------ 内部工具
def _pick(raw: Dict[str, Any], keys: tuple) -> Any:
    for key in keys:
        if key in raw and raw[key] not in (None, ""):
            return raw[key]
        # 大小写不敏感兜底
        for actual in raw.keys():
            if str(actual).lower() == key.lower() and raw[actual] not in (None, ""):
                return raw[actual]
    return None


def _as_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    if isinstance(value, (list, tuple)):
        return "、".join(_as_text(v) for v in value)
    return str(value)


def _norm_type(raw_type: str, options: List[Dict[str, str]], raw_answer: Any) -> str:
    """规范化题型；缺失时按选项/答案推断。"""
    key = re.sub(r"[\s_\-]+", "", (raw_type or "")).lower()
    if key in _TYPE_ALIASES:
        return _TYPE_ALIASES[key]
    if options:
        if _answer_key_count(raw_answer) > 1:
            return TYPE_MULTIPLE
        return TYPE_SINGLE
    answer_text = _as_text(raw_answer).strip().lower()
    if answer_text in _TRUE_WORDS or answer_text in _FALSE_WORDS:
        return TYPE_JUDGE
    if not options and not answer_text:
        return TYPE_SHORT
    return TYPE_SHORT


def _answer_key_count(raw_answer: Any) -> int:
    if isinstance(raw_answer, (list, tuple)):
        return len(raw_answer)
    if isinstance(raw_answer, str):
        cleaned = _ANSWER_NOISE_RE.sub("", raw_answer)
        return len({m.lower() for m in _ANY_KEY_RE.findall(cleaned) if m})
    return 0


def _norm_options(raw_options: Any) -> List[Dict[str, str]]:
    """把各种选项写法统一成 [{"key": "A", "text": "..."}]。"""
    if not raw_options:
        return []
    result: List[Dict[str, str]] = []

    if isinstance(raw_options, dict):
        for key, text in raw_options.items():
            result.append({"key": str(key).strip().upper(), "text": _as_text(text)})
        return result

    if isinstance(raw_options, (list, tuple)):
        for index, item in enumerate(raw_options):
            default_key = chr(ord("A") + index) if index < 26 else str(index + 1)
            if isinstance(item, dict):
                key = _as_text(_pick(item, ("key", "label", "k", "选项", "name", "id"))).strip()
                text = _as_text(_pick(item, ("text", "value", "v", "content", "选项内容")))
                if not text:
                    text = _as_text(item.get("value"))
                result.append({"key": (key or default_key).upper(), "text": text})
            else:
                text = _as_text(item)
                match = _OPTION_PREFIX_RE.match(text)
                if match:
                    result.append({"key": match.group(1).upper(), "text": text[match.end():].strip()})
                else:
                    result.append({"key": default_key, "text": text.strip()})
        return result

    return result


def _norm_answer(raw_answer: Any, qtype: str, options: List[Dict[str, str]]) -> Any:
    """规范化答案。

    产出规则（与题库 JSON 约定一致）：
      - single  -> "A"
      - multiple-> ["A", "B"]（去重 + 排序）
      - judge   -> true / false
      - short   -> "参考答案文本"
    """
    option_keys = [item["key"] for item in options]

    if qtype == TYPE_JUDGE:
        return _norm_judge_answer(raw_answer)

    if qtype == TYPE_MULTIPLE:
        keys = _extract_keys(raw_answer, option_keys)
        if keys:
            return sorted(keys)
        matched = _match_option_text(raw_answer, options)
        if matched:
            return [matched]
        text = _as_text(raw_answer).strip()
        return [text] if text else []

    if qtype == TYPE_SINGLE:
        keys = _extract_keys(raw_answer, option_keys)
        if keys:
            return keys[0]
        # 答案写成选项原文时，反查选项字母
        matched = _match_option_text(raw_answer, options)
        if matched:
            return matched
        return _as_text(raw_answer).strip()

    # 简答：保留文本
    return _as_text(raw_answer).strip()


def _match_option_text(raw_answer: Any, options: List[Dict[str, str]]) -> str:
    """答案写成选项原文时，反查对应选项字母。"""
    cleaned = normalize_text(_as_text(raw_answer))
    if not cleaned:
        return ""
    for option in options:
        if normalize_text(option.get("text")) == cleaned:
            return option["key"]
    return ""


def _norm_judge_answer(raw_answer: Any) -> Optional[bool]:
    if isinstance(raw_answer, bool):
        return raw_answer
    if isinstance(raw_answer, (int, float)):
        return bool(raw_answer)
    if isinstance(raw_answer, (list, tuple)):
        for item in raw_answer:
            value = _norm_judge_answer(item)
            if value is not None:
                return value
        return None
    text = _ANSWER_NOISE_RE.sub("", _as_text(raw_answer)).strip().lower()
    if text in _TRUE_WORDS:
        return True
    if text in _FALSE_WORDS:
        return False
    return None


def _extract_keys(raw_answer: Any, option_keys: List[str]) -> List[str]:
    """从答案里抽出选项字母。"""
    candidates: List[str] = []
    if isinstance(raw_answer, (list, tuple)):
        for item in raw_answer:
            candidates.extend(_extract_keys(item, option_keys))
        return _dedup_keep_order(candidates)

    text = _ANSWER_NOISE_RE.sub("", _as_text(raw_answer)).strip()
    if not text:
        return []

    single = _KEY_RE.match(text)
    if single:
        return [single.group(1).upper()]

    # 只有「纯字母 + 分隔符」的写法才按字母抽取，避免把单词误判成选项
    if not _PURE_KEYS_RE.match(text):
        return []

    letters = [m.upper() for m in _ANY_KEY_RE.findall(text)]
    if option_keys:
        valid = [letter for letter in letters if letter in set(option_keys)]
        # 仅当抽出的字母数量不超过选项数量时才认为靠谱
        if valid and len(valid) <= len(option_keys):
            return _dedup_keep_order(valid)
        return []
    return _dedup_keep_order(letters)


def _dedup_keep_order(items: List[str]) -> List[str]:
    seen = set()
    out = []
    for item in items:
        if item and item not in seen:
            seen.add(item)
            out.append(item)
    return out


__all__ = [
    "NormalizedQuestion",
    "QuestionFormatError",
    "parse_question_bank",
    "normalize_question",
    "QUESTION_TYPES",
]
