# -*- coding: utf-8 -*-
# SPDX-FileCopyrightText: 2026 梁小军 (GitHub: Jun-Leon)
# SPDX-License-Identifier: MIT
"""统计看板路由：一次返回概览、分布、趋势与高频错题。

数据全部限定在「当前档案」范围内，切换档案即切换统计口径。
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import current_profile
from ..models import Profile
from ..schemas import StatsBoardOut
from ..services.stats_service import TREND_DAYS, StatsService

router = APIRouter(prefix="/stats", tags=["stats"])


@router.get("/board", response_model=StatsBoardOut)
def stats_board(
    trend_days: int = Query(
        default=TREND_DAYS, ge=7, le=90, description="趋势图统计天数（7~90）"
    ),
    db: Session = Depends(get_db),
    profile: Profile = Depends(current_profile),
) -> StatsBoardOut:
    """当前档案的刷题统计看板数据。"""
    return StatsBoardOut(**StatsService(db, profile.id).board(trend_days))
