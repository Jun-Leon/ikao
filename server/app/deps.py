# -*- coding: utf-8 -*-
# SPDX-FileCopyrightText: 2026 梁小军 (GitHub: Jun-Leon)
# SPDX-License-Identifier: MIT
"""FastAPI 公共依赖：当前档案（离线多用户的核心）。"""

from __future__ import annotations

from fastapi import Depends
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .database import get_db
from .models import Profile
from .utils.settings_store import get_setting

CURRENT_PROFILE_KEY = "current_profile_id"
DEFAULT_PROFILE_NAME = "默认档案"


def _find_profile(db: Session) -> Profile | None:
    profile = db.scalar(select(Profile).where(Profile.is_default.is_(True)))
    if profile is None:
        profile = db.scalar(select(Profile).order_by(Profile.id))
    return profile


def ensure_default_profile(db: Session) -> Profile:
    """保证至少存在一个档案，并返回默认档案。"""
    profile = _find_profile(db)
    if profile is not None:
        return profile

    profile = Profile(name=DEFAULT_PROFILE_NAME, is_default=True)
    db.add(profile)
    try:
        db.commit()
    except IntegrityError:
        # 首屏前端会并发请求多个接口，可能与其它请求同时建默认档案，回滚后复用已建好的那条
        db.rollback()
        profile = _find_profile(db)
        if profile is None:
            raise
        return profile
    db.refresh(profile)
    return profile


def get_current_profile(db: Session) -> Profile:
    """取当前档案；若设置里记录的档案已不存在则回退到默认档案。"""
    raw = get_setting(db, CURRENT_PROFILE_KEY)
    if raw:
        try:
            profile = db.get(Profile, int(raw))
        except (TypeError, ValueError):
            profile = None
        if profile is not None:
            return profile
    profile = ensure_default_profile(db)
    set_current_profile(db, profile.id)
    return profile


def set_current_profile(db: Session, profile_id: int) -> None:
    from .utils.settings_store import set_setting

    set_setting(db, CURRENT_PROFILE_KEY, str(profile_id))


def current_profile(db: Session = Depends(get_db)) -> Profile:
    """FastAPI 依赖：取当前档案（刷题接口全部以它隔离数据）。"""
    return get_current_profile(db)
