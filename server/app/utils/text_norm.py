# -*- coding: utf-8 -*-
"""文本归一化：用于题干去重比较。

注意：这里**不改动**题目原文，只是另外生成一份「归一化副本」用于比较，
所以 LaTeX 公式在原文里始终原样保留，渲染不受影响。
"""

from __future__ import annotations

import hashlib
import re
import unicodedata

# 需要剔除的标点/空白（中英文标点与各类空格）
_PUNCT_RE = re.compile(
    r"[\s\u3000"
    r"!-/:-@\[-`{-~"
    r"\u3001-\u303f\uff01-\uff0f\uff1a-\uff20\uff3b-\uff40\uff5b-\uff65"
    r"]+"
)

# LaTeX 命令（如 \frac、\alpha）与定界符：归一化时可选择性剥离
_LATEX_CMD_RE = re.compile(r"\\[a-zA-Z]+")
_MATH_DELIM_RE = re.compile(r"\$+")
_HTML_TAG_RE = re.compile(r"<[^>]+>")
# 常见题干前缀：不影响「是否同一题」的判断
_STEM_PREFIX_RE = re.compile(r"^\s*(?:第\s*\d+\s*题|[（(]?\d+[)）.、]\s*)")


def normalize_text(text: str | None) -> str:
    """通用归一化：去 HTML、全角转半角、去标点空白、转小写。"""
    if not text:
        return ""
    out = _HTML_TAG_RE.sub("", str(text))
    # NFKC：全角字母数字 -> 半角，兼容字符 -> 标准字符
    out = unicodedata.normalize("NFKC", out)
    out = _PUNCT_RE.sub("", out)
    return out.lower().strip()


def normalize_stem(title: str | None, *, keep_latex_cmd: bool = False) -> str:
    """题干归一化。

    keep_latex_cmd=False（默认）：把 ``\\frac`` 之类的命令名也剥掉，
    只留下公式里的实际内容，避免不同写法（``x^{2}`` / ``x^2``）导致漏判重复。
    """
    if not title:
        return ""
    raw = str(title)
    raw = _STEM_PREFIX_RE.sub("", raw)
    if not keep_latex_cmd:
        raw = _LATEX_CMD_RE.sub("", raw)
        raw = _MATH_DELIM_RE.sub("", raw)
    return normalize_text(raw)


def md5_hash(text: str | None) -> str:
    """md5 摘要（用于题库指纹、题干精确去重）。"""
    return hashlib.md5((text or "").encode("utf-8")).hexdigest()


def make_preview(text: str | None, limit: int = 60) -> str:
    """生成题干摘要，用于日志列表展示。"""
    if not text:
        return ""
    flat = re.sub(r"\s+", " ", str(text)).strip()
    return flat if len(flat) <= limit else flat[:limit] + "..."
