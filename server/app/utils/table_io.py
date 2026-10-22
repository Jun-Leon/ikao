# -*- coding: utf-8 -*-
# SPDX-FileCopyrightText: 2026 梁小军 (GitHub: Jun-Leon)
# SPDX-License-Identifier: MIT
"""表格题库读写（CSV / Excel）。

设计目标：让「下载模板 -> 填写 -> 上传」与「导出 CSV」共用同一套列定义，
导出的文件可以直接改完再导入，不需要手工调整列。

列定义（顺序固定）::

    编号 | 题型 | 题干 | 选项A | 选项B | ... | 选项H | 答案 | 解析

读取时只要求「题干」列存在，其余列可缺省、顺序可乱、列名大小写不敏感。
"""

from __future__ import annotations

import csv
import io
import json
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

# ------------------------------------------------------------------ 列定义
COL_EXT_ID = "编号"
COL_TYPE = "题型"
COL_TITLE = "题干"
COL_ANSWER = "答案"
COL_ANALYSIS = "解析"

OPTION_LETTERS: tuple = tuple("ABCDEFGH")
OPTION_COLUMNS: tuple = tuple(f"选项{letter}" for letter in OPTION_LETTERS)

TABLE_HEADERS: tuple = (
    COL_EXT_ID,
    COL_TYPE,
    COL_TITLE,
    *OPTION_COLUMNS,
    COL_ANSWER,
    COL_ANALYSIS,
)

EXCEL_SUFFIXES = (".xlsx", ".xlsm")
CSV_SUFFIXES = (".csv", ".txt")
TEXT_ENCODINGS = ("utf-8-sig", "utf-8", "gb18030", "utf-16")

_XLSX_MAGIC = b"PK\x03\x04"

_TITLE_ALIASES = {"题干", "题目", "问题", "标题", "title", "stem", "question", "content"}
_TYPE_ALIASES = {"题型", "类型", "type", "kind", "qtype"}
_ANSWER_ALIASES = {"答案", "正确答案", "参考答案", "answer", "answers", "correct", "correct_answer"}
_ANALYSIS_ALIASES = {"解析", "分析", "说明", "analysis", "explanation", "analyze"}
_EXT_ID_ALIASES = {"编号", "题号", "id", "qid", "code"}
_OPTIONS_ALIASES = {"选项", "options", "choices", "option"}

_OPTION_HEADER_RE = re.compile(r"^(?:选项|option|opt)\s*([A-Za-z])$")


class TableFormatError(ValueError):
    """表格文件无法解析（结构 / 编码 / 列缺失）。"""


# ------------------------------------------------------------------ 读取
def decode_text(data: bytes) -> str:
    """按常见编码依次尝试解码文本（UTF-8 优先，兼顾 GBK 环境下的 CSV）。"""
    for encoding in TEXT_ENCODINGS:
        try:
            return data.decode(encoding)
        except UnicodeDecodeError:
            continue
    raise TableFormatError("文件编码无法识别，请另存为 UTF-8 后重试")


def parse_table_bytes(data: bytes, filename: str = "") -> List[Dict[str, Any]]:
    """把 CSV / Excel 文件解析成「原始题目字典列表」，可直接交给 normalize_question。

    :raises TableFormatError: 文件类型不支持 / 结构无法识别 / 没有可用数据行
    """
    suffix = Path(filename or "").suffix.lower()

    if suffix in EXCEL_SUFFIXES:
        rows = _read_excel_rows(data)
    elif suffix in CSV_SUFFIXES:
        rows = _read_csv_rows(data)
    elif suffix == ".xls":
        raise TableFormatError("不支持旧版 .xls 格式，请在 Excel/WPS 中另存为 .xlsx 后重试")
    elif not suffix and data[:4] == _XLSX_MAGIC:
        rows = _read_excel_rows(data)
    elif not suffix:
        rows = _read_csv_rows(data)
    else:
        raise TableFormatError(f"仅支持 .csv / .xlsx / .xlsm 文件，当前为 {suffix}")

    return _rows_to_raw_items(rows)


def _read_csv_rows(data: bytes) -> List[List[str]]:
    text = decode_text(data)
    reader = csv.reader(io.StringIO(text, newline=""))
    return [[cell.strip() for cell in row] for row in reader]


def _read_excel_rows(data: bytes) -> List[List[str]]:
    try:
        import openpyxl
    except ImportError as exc:  # pragma: no cover 缺少依赖时给出明确指引
        raise TableFormatError("缺少 openpyxl 依赖，请执行 pip install openpyxl") from exc

    try:
        workbook = openpyxl.load_workbook(
            io.BytesIO(data), read_only=True, data_only=True
        )
    except Exception as exc:  # noqa: BLE001 openpyxl 抛出的异常类型较多
        raise TableFormatError(f"Excel 文件无法读取：{exc}") from exc

    try:
        sheet = workbook.worksheets[0]
        rows: List[List[str]] = []
        for values in sheet.iter_rows(values_only=True):
            rows.append([_cell_text(cell) for cell in values])
        return rows
    finally:
        workbook.close()


def _cell_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, float) and value.is_integer():
        # Excel 会把整数读成 1.0，避免答案列变成 "1.0"
        return str(int(value))
    return str(value).strip()


def _rows_to_raw_items(rows: Sequence[Sequence[str]]) -> List[Dict[str, Any]]:
    """定位表头行 -> 映射列 -> 逐行产出原始题目字典。"""
    header_index, columns = _locate_header(rows)
    if COL_TITLE not in columns.values():
        raise TableFormatError(
            f"未找到「{COL_TITLE}」列，请使用下载的 Excel 模板或保留题干列名"
        )

    items: List[Dict[str, Any]] = []
    for row in rows[header_index + 1:]:
        item = _row_to_raw_item(row, columns)
        if item is not None:
            items.append(item)

    if not items:
        raise TableFormatError("表格中没有可导入的题目数据行")
    return items


def _locate_header(rows: Sequence[Sequence[str]]) -> tuple:
    """返回 (表头行下标, {列下标: 字段名})；字段名已归一化为模板列名。"""
    for index, row in enumerate(rows):
        columns: Dict[int, str] = {}
        for col_index, raw_name in enumerate(row):
            field = _match_header(raw_name)
            if field and col_index not in columns:
                columns[col_index] = field
        if columns:
            return index, columns
    raise TableFormatError("表格为空或缺少表头行")


def _match_header(raw_name: str) -> Optional[str]:
    name = (raw_name or "").strip()
    if not name:
        return None

    match = _OPTION_HEADER_RE.match(name)
    if match:
        letter = match.group(1).upper()
        if letter in OPTION_LETTERS:
            return f"选项{letter}"
        return None

    lowered = name.lower().replace(" ", "")
    if name in _TITLE_ALIASES or lowered in _TITLE_ALIASES:
        return COL_TITLE
    if name in _TYPE_ALIASES or lowered in _TYPE_ALIASES:
        return COL_TYPE
    if name in _ANSWER_ALIASES or lowered in _ANSWER_ALIASES:
        return COL_ANSWER
    if name in _ANALYSIS_ALIASES or lowered in _ANALYSIS_ALIASES:
        return COL_ANALYSIS
    if name in _EXT_ID_ALIASES or lowered in _EXT_ID_ALIASES:
        return COL_EXT_ID
    if name in _OPTIONS_ALIASES or lowered in _OPTIONS_ALIASES:
        # 「选项」单列：内容形如 "A. xx B. yy"
        return "选项"
    return None


def _row_to_raw_item(row: Sequence[str], columns: Dict[int, str]) -> Optional[Dict[str, Any]]:
    values: Dict[str, str] = {}
    for col_index, field in columns.items():
        if col_index < len(row):
            text = (row[col_index] or "").strip()
            if text:
                values[field] = text

    if not values:
        return None

    raw: Dict[str, Any] = {}
    if COL_TITLE in values:
        raw["title"] = values[COL_TITLE]
    if COL_TYPE in values:
        raw["type"] = values[COL_TYPE]
    if COL_ANSWER in values:
        raw["answer"] = values[COL_ANSWER]
    if COL_ANALYSIS in values:
        raw["analysis"] = values[COL_ANALYSIS]
    if COL_EXT_ID in values:
        raw["id"] = values[COL_EXT_ID]

    options = [
        {"key": letter, "text": values[f"选项{letter}"]}
        for letter in OPTION_LETTERS
        if f"选项{letter}" in values
    ]
    if not options and "选项" in values:
        options = _split_inline_options(values["选项"])
    if options:
        raw["options"] = options

    # 整行只有编号也算空行，跳过
    if set(raw.keys()) <= {"id"}:
        return None
    return raw


def _split_inline_options(text: str) -> List[Dict[str, str]]:
    """把「选项」单列拆成选项列表，支持 A. xx / A、xx / A) xx，也支持换行与 | 分隔。"""
    parts = re.split(r"[\n\r|；;]+", text)
    options: List[Dict[str, str]] = []
    for part in parts:
        piece = part.strip()
        if not piece:
            continue
        match = re.match(r"^\s*[（(\[]?([A-Za-z])[)）\].、:：]\s*", piece)
        if match:
            options.append({"key": match.group(1).upper(), "text": piece[match.end():].strip()})
        else:
            key = chr(ord("A") + len(options)) if len(options) < 26 else str(len(options) + 1)
            options.append({"key": key, "text": piece})
    return options


# ------------------------------------------------------------------ 模板
def build_template_xlsx() -> bytes:
    """生成 Excel 题库模板（含示例行与填写说明）。"""
    import openpyxl
    from openpyxl.styles import Alignment, Font, PatternFill

    workbook = openpyxl.Workbook()
    sheet = workbook.active
    sheet.title = "题目"

    header_font = Font(bold=True, color="FFFFFF")
    header_fill = PatternFill("solid", fgColor="3A8AFF")
    wrap = Alignment(vertical="top", wrap_text=True)

    sheet.append(list(TABLE_HEADERS))
    for cell in sheet[1]:
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = Alignment(vertical="center", horizontal="center")

    samples = [
        ["1", "单选", "TCP 协议工作在 OSI 参考模型的哪一层？", "传输层", "网络层", "会话层", "应用层",
         "", "", "", "", "A", "TCP 是传输层协议，提供面向连接的可靠传输。"],
        ["2", "多选", "以下哪些属于 HTTP 请求方法？", "GET", "POST", "TCP", "PUT",
         "", "", "", "", "A,B,D", "TCP 是传输层协议，不属于 HTTP 请求方法。"],
        ["3", "判断", "IPv4 地址长度为 32 位。", "", "", "", "",
         "", "", "", "", "正确", "IPv4 为 32 位，IPv6 为 128 位。"],
        ["4", "简答", "简述 TCP 三次握手的过程。", "", "", "", "",
         "", "", "", "", "客户端发送 SYN；服务端回复 SYN+ACK；客户端再发送 ACK。", ""],
    ]
    for row in samples:
        sheet.append(row)

    sheet.freeze_panes = "A2"
    widths = {1: 8, 2: 8, 3: 46, 12: 14, 13: 40}
    for index in range(1, len(TABLE_HEADERS) + 1):
        letter = sheet.cell(row=1, column=index).column_letter
        sheet.column_dimensions[letter].width = widths.get(index, 14)
    for row in sheet.iter_rows(min_row=2):
        for cell in row:
            cell.alignment = wrap

    guide = workbook.create_sheet("填写说明")
    guide.append(["列名", "是否必填", "填写说明"])
    guide_rows = [
        [COL_TITLE, "必填", "题目正文，支持 LaTeX 公式，例如 $x^2+y^2=z^2$"],
        [COL_TYPE, "选填", "single/单选、multiple/多选、judge/判断、short/简答；留空时按选项与答案自动推断"],
        [COL_ANSWER, "选填", "单选填选项字母（如 A）；多选填多个字母（如 A,B 或 AB）；判断填 正确/错误；简答填参考答案文本"],
        [COL_ANALYSIS, "选填", "答案解析，支持 LaTeX 公式"],
        [COL_EXT_ID, "选填", "题目原始编号，仅作标记，不参与判分"],
        ["选项A ~ 选项H", "选择题必填", "每列填一个选项内容，不要写「A.」前缀；判断题与简答题留空"],
    ]
    for row in guide_rows:
        guide.append(row)
    guide.column_dimensions["A"].width = 18
    guide.column_dimensions["B"].width = 12
    guide.column_dimensions["C"].width = 70
    for cell in guide[1]:
        cell.font = header_font
        cell.fill = header_fill
    for row in guide.iter_rows(min_row=1):
        for cell in row:
            cell.alignment = wrap

    buffer = io.BytesIO()
    workbook.save(buffer)
    return buffer.getvalue()


TEMPLATE_FILENAME = "ikao-question-template.xlsx"
XLSX_MEDIA_TYPE = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
CSV_MEDIA_TYPE = "text/csv; charset=utf-8"


# ------------------------------------------------------------------ 导出
def question_to_cells(question: Any) -> List[str]:
    """把 ORM 题目行转成一行表格单元格（列顺序与 TABLE_HEADERS 一致）。"""
    options = _load_json(question.options, [])
    by_key = {
        str(item.get("key", "")).upper(): str(item.get("text", ""))
        for item in options
        if isinstance(item, dict)
    }

    answer = _load_json(question.answer, question.answer)
    cells = [
        question.ext_id or "",
        question.type or "",
        question.title or "",
    ]
    cells.extend(by_key.get(letter, "") for letter in OPTION_LETTERS)
    cells.append(_format_answer(question.type, answer))
    cells.append(question.analysis or "")
    return cells


def build_questions_csv(questions: Sequence[Any]) -> bytes:
    """把题目列表导出为 CSV 字节流（带 BOM，Excel 双击打开不乱码）。"""
    buffer = io.StringIO(newline="")
    writer = csv.writer(buffer)
    writer.writerow(TABLE_HEADERS)
    for question in questions:
        writer.writerow(question_to_cells(question))
    return ("\ufeff" + buffer.getvalue()).encode("utf-8")


def _format_answer(qtype: str, answer: Any) -> str:
    if qtype == "judge":
        if answer is True:
            return "正确"
        if answer is False:
            return "错误"
        return ""
    if isinstance(answer, (list, tuple)):
        return ",".join(str(item) for item in answer)
    if answer is None:
        return ""
    return str(answer)


def _load_json(value: Any, default: Any) -> Any:
    if value is None or value == "":
        return default
    if isinstance(value, (list, dict)):
        return value
    try:
        return json.loads(value)
    except (TypeError, ValueError):
        return default


__all__ = [
    "TableFormatError",
    "TABLE_HEADERS",
    "OPTION_COLUMNS",
    "OPTION_LETTERS",
    "TEMPLATE_FILENAME",
    "XLSX_MEDIA_TYPE",
    "CSV_MEDIA_TYPE",
    "decode_text",
    "parse_table_bytes",
    "build_template_xlsx",
    "build_questions_csv",
    "question_to_cells",
]
