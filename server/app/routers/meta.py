# -*- coding: utf-8 -*-
"""基础信息路由：健康检查、前端启动元信息。"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..config import settings
from ..database import get_db
from ..deps import get_current_profile
from ..schemas import HealthOut, MetaOut
from ..services.import_service import count_questions

router = APIRouter(tags=["meta"])


@router.get("/health", response_model=HealthOut)
def health(db: Session = Depends(get_db)) -> HealthOut:
    return HealthOut(
        status="ok",
        app=settings.app_name,
        version=settings.version,
        database=settings.sqlalchemy_url,
        question_count=count_questions(db),
    )


@router.get("/meta", response_model=MetaOut)
def meta(db: Session = Depends(get_db)) -> MetaOut:
    profile = get_current_profile(db)
    return MetaOut(
        app_name=settings.app_name,
        version=settings.version,
        dedup_threshold=settings.dedup_threshold,
        question_count=count_questions(db),
        current_profile_id=profile.id,
        current_profile_name=profile.name,
    )
