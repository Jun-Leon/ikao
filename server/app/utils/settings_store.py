# -*- coding: utf-8 -*-
# SPDX-FileCopyrightText: 2026 梁小军 (GitHub: Jun-Leon)
# SPDX-License-Identifier: MIT
"""app_setting 键值配置读写。"""

from __future__ import annotations

from typing import Optional

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..models import AppSetting


def get_setting(db: Session, key: str, default: Optional[str] = None) -> Optional[str]:
    row = db.get(AppSetting, key)
    return row.value if row is not None else default


def set_setting(db: Session, key: str, value: str) -> None:
    row = db.get(AppSetting, key)
    if row is None:
        db.add(AppSetting(key=key, value=value))
    else:
        row.value = value
    try:
        db.commit()
    except IntegrityError:
        # 并发请求可能同时写入同一个键，回滚后改为更新已有行
        db.rollback()
        row = db.get(AppSetting, key)
        if row is None:
            raise
        row.value = value
        db.commit()
