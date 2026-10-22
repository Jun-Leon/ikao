# -*- coding: utf-8 -*-
# SPDX-FileCopyrightText: 2026 梁小军 (GitHub: Jun-Leon)
# SPDX-License-Identifier: MIT
"""导入路由：题库导入（JSON / CSV / Excel）+ 模板下载 + 导入日志查询。"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, Response, UploadFile
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import ImportLog, ImportLogItem
from ..schemas import (
    ImportLogDetailOut,
    ImportLogItemOut,
    ImportLogOut,
    ImportLogPageOut,
    ImportResultOut,
)
from ..services.import_service import ImportService, get_log_detail
from ..utils.table_io import (
    TEMPLATE_FILENAME,
    XLSX_MEDIA_TYPE,
    TableFormatError,
    build_template_xlsx,
    decode_text,
    parse_table_bytes,
)
from ..utils.text_norm import md5_hash

router = APIRouter(prefix="/import", tags=["import"])

_MAX_UPLOAD_BYTES = 32 * 1024 * 1024  # 单文件上限 32MB


@router.post("/json", response_model=ImportResultOut)
async def import_json(
    file: Optional[UploadFile] = File(default=None, description="题库 JSON 文件"),
    path: Optional[str] = Form(default=None, description="或填写本机 JSON 文件绝对路径"),
    threshold: Optional[float] = Form(default=None, description="去重阈值 0~1，默认取配置"),
    db: Session = Depends(get_db),
) -> ImportResultOut:
    """导入题库 JSON（二选一：上传文件 / 指定本地路径）。"""
    source_name, raw_text = await _read_payload(file, path)
    _check_threshold(threshold)

    service = ImportService(db)
    log = service.import_text(raw_text, source_name=source_name, threshold=threshold)
    return _to_result(log)


@router.post("/table", response_model=ImportResultOut)
async def import_table(
    file: UploadFile = File(..., description="CSV / Excel 题库文件（.csv / .xlsx）"),
    threshold: Optional[float] = Form(default=None, description="去重阈值 0~1，默认取配置"),
    db: Session = Depends(get_db),
) -> ImportResultOut:
    """导入 CSV / Excel 题库（建议先下载模板，按列填写后上传）。"""
    _check_threshold(threshold)

    source_name = file.filename or "uploaded.table"
    data = await file.read()
    if len(data) > _MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="文件过大（上限 32MB）")

    try:
        raw_items = parse_table_bytes(data, source_name)
    except TableFormatError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    log = ImportService(db).import_items(
        raw_items,
        source_name=source_name,
        threshold=threshold,
        file_hash=md5_hash(data),
    )
    return _to_result(log)


@router.get("/template")
def download_template() -> Response:
    """下载 Excel 题库模板（含示例行与填写说明）。"""
    return Response(
        content=build_template_xlsx(),
        media_type=XLSX_MEDIA_TYPE,
        headers={"Content-Disposition": f'attachment; filename="{TEMPLATE_FILENAME}"'},
    )


@router.get("/logs", response_model=ImportLogPageOut)
def list_logs(
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    status: Optional[str] = Query(default=None, description="success / partial / failed"),
    db: Session = Depends(get_db),
) -> ImportLogPageOut:
    """导入日志分页列表（按时间倒序）。"""
    stmt = select(ImportLog)
    count_stmt = select(func.count(ImportLog.id))
    if status:
        stmt = stmt.where(ImportLog.status == status)
        count_stmt = count_stmt.where(ImportLog.status == status)

    total = int(db.scalar(count_stmt) or 0)
    rows = (
        db.execute(
            stmt.order_by(ImportLog.created_at.desc(), ImportLog.id.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        .scalars()
        .all()
    )
    return ImportLogPageOut(
        total=total,
        page=page,
        page_size=page_size,
        items=[ImportLogOut.from_row(row) for row in rows],
    )


@router.get("/logs/{log_id}", response_model=ImportLogDetailOut)
def log_detail(
    log_id: int,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
    status: Optional[str] = Query(default=None, description="success / duplicate / failed"),
    db: Session = Depends(get_db),
) -> ImportLogDetailOut:
    """导入日志详情：逐条明细。"""
    found = get_log_detail(db, log_id)
    if found is None:
        raise HTTPException(status_code=404, detail="导入日志不存在")
    log, _ = found

    stmt = select(ImportLogItem).where(ImportLogItem.log_id == log_id)
    count_stmt = select(func.count(ImportLogItem.id)).where(ImportLogItem.log_id == log_id)
    if status:
        stmt = stmt.where(ImportLogItem.status == status)
        count_stmt = count_stmt.where(ImportLogItem.status == status)

    items_total = int(db.scalar(count_stmt) or 0)
    rows = (
        db.execute(
            stmt.order_by(ImportLogItem.row_index.asc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        .scalars()
        .all()
    )
    return ImportLogDetailOut(
        log=ImportLogOut.from_row(log),
        items_total=items_total,
        page=page,
        page_size=page_size,
        items=[ImportLogItemOut.from_row(row) for row in rows],
    )


@router.delete("/logs/{log_id}")
def delete_log(log_id: int, db: Session = Depends(get_db)) -> dict:
    """删除一条导入日志（仅删日志，不动已入库题目）。"""
    log = db.get(ImportLog, log_id)
    if log is None:
        raise HTTPException(status_code=404, detail="导入日志不存在")
    db.delete(log)
    db.commit()
    return {"ok": True}


# ------------------------------------------------------------------ 内部工具
def _check_threshold(threshold: Optional[float]) -> None:
    if threshold is not None and not 0.0 <= threshold <= 1.0:
        raise HTTPException(status_code=400, detail="threshold 必须在 0~1 之间")


def _to_result(log: ImportLog) -> ImportResultOut:
    return ImportResultOut(
        log_id=log.id,
        source_name=log.source_name,
        total=log.total,
        imported=log.imported,
        duplicated=log.duplicated,
        failed=log.failed,
        threshold=log.threshold,
        status=log.status,
        message=log.message,
    )


async def _read_payload(file: Optional[UploadFile], path: Optional[str]) -> tuple[str, str]:
    """读取导入内容，返回 (来源名, JSON 文本)。"""
    if file is not None and file.filename:
        data = await file.read()
        if len(data) > _MAX_UPLOAD_BYTES:
            raise HTTPException(status_code=413, detail="文件过大（上限 32MB）")
        return file.filename, _decode(data)

    if path:
        target = Path(path).expanduser()
        if not target.is_file():
            raise HTTPException(status_code=400, detail=f"文件不存在：{target}")
        if target.stat().st_size > _MAX_UPLOAD_BYTES:
            raise HTTPException(status_code=413, detail="文件过大（上限 32MB）")
        return target.name, _decode(target.read_bytes())

    raise HTTPException(status_code=400, detail="请上传 JSON 文件，或填写本地文件路径")


def _decode(data: bytes) -> str:
    try:
        return decode_text(data)
    except TableFormatError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
