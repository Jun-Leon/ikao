# -*- coding: utf-8 -*-
# SPDX-FileCopyrightText: 2026 梁小军 (GitHub: Jun-Leon)
# SPDX-License-Identifier: MIT
"""档案路由：离线多用户的数据隔离载体（不登录，切换档案）。"""

from __future__ import annotations

from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import DEFAULT_PROFILE_NAME, ensure_default_profile, get_current_profile, set_current_profile
from ..models import Profile
from ..schemas import ProfileCreateIn, ProfileOut

router = APIRouter(prefix="/profiles", tags=["profiles"])


@router.get("", response_model=List[ProfileOut])
def list_profiles(db: Session = Depends(get_db)) -> List[ProfileOut]:
    ensure_default_profile(db)
    rows = db.execute(select(Profile).order_by(Profile.id.asc())).scalars().all()
    return [ProfileOut.from_row(row) for row in rows]


@router.post("", response_model=ProfileOut)
def create_profile(payload: ProfileCreateIn, db: Session = Depends(get_db)) -> ProfileOut:
    name = payload.name.strip()
    if not name:
        raise HTTPException(status_code=400, detail="档案名称不能为空")
    exists = db.scalar(select(Profile).where(Profile.name == name))
    if exists is not None:
        raise HTTPException(status_code=409, detail="同名档案已存在")
    profile = Profile(name=name, is_default=False)
    db.add(profile)
    db.commit()
    db.refresh(profile)
    return ProfileOut.from_row(profile)


@router.post("/{profile_id}/switch", response_model=ProfileOut)
def switch_profile(profile_id: int, db: Session = Depends(get_db)) -> ProfileOut:
    profile = db.get(Profile, profile_id)
    if profile is None:
        raise HTTPException(status_code=404, detail="档案不存在")
    set_current_profile(db, profile.id)
    return ProfileOut.from_row(profile)


@router.get("/current", response_model=ProfileOut)
def current_profile(db: Session = Depends(get_db)) -> ProfileOut:
    return ProfileOut.from_row(get_current_profile(db))


@router.delete("/{profile_id}")
def delete_profile(profile_id: int, db: Session = Depends(get_db)) -> dict:
    """删除档案（连同该档案的作答记录，由外键级联清理）。"""
    profile = db.get(Profile, profile_id)
    if profile is None:
        raise HTTPException(status_code=404, detail="档案不存在")

    total = len(db.execute(select(Profile.id)).scalars().all())
    if total <= 1:
        raise HTTPException(status_code=400, detail="至少保留一个档案")

    if profile.is_default:
        raise HTTPException(status_code=400, detail=f"默认档案（{DEFAULT_PROFILE_NAME}）不可删除")

    current = get_current_profile(db)
    db.delete(profile)
    db.commit()

    if current.id == profile_id:
        fallback = ensure_default_profile(db)
        set_current_profile(db, fallback.id)
    return {"ok": True}
