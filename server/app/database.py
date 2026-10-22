# -*- coding: utf-8 -*-
"""数据库连接与会话管理（SQLAlchemy 2.x + SQLite）。"""

from __future__ import annotations

from collections.abc import Generator

from sqlalchemy import create_engine, event
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from .config import settings


class Base(DeclarativeBase):
    """所有 ORM 模型的基类。"""


engine = create_engine(
    settings.sqlalchemy_url,
    echo=False,
    future=True,
    # SQLite + FastAPI 多线程需要关闭同线程检查
    connect_args={"check_same_thread": False},
)


@event.listens_for(engine, "connect")
def _set_sqlite_pragma(dbapi_connection, _connection_record) -> None:
    """连接建立时统一开启外键约束与 WAL 日志模式。"""
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.close()


SessionLocal = sessionmaker(
    bind=engine,
    autoflush=False,
    autocommit=False,
    expire_on_commit=False,
)


def init_db() -> None:
    """建表（幂等，可重复执行）。"""
    from . import models  # noqa: F401  触发模型注册到 Base.metadata

    settings.data_dir.mkdir(parents=True, exist_ok=True)
    Base.metadata.create_all(bind=engine)


def get_db() -> Generator[Session, None, None]:
    """FastAPI 依赖：每个请求一个数据库会话。"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
