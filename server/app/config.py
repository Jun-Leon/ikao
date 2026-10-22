# -*- coding: utf-8 -*-
# SPDX-FileCopyrightText: 2026 梁小军 (GitHub: Jun-Leon)
# SPDX-License-Identifier: MIT
"""全局配置。

统一从环境变量 / .env 读取配置（前缀 IKAO_），供各模块复用。
兼容 PyInstaller 打包场景（sys._MEIPASS）。
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import List

from pydantic_settings import BaseSettings, SettingsConfigDict


def _server_dir() -> Path:
    """server/ 目录（源码运行时的绝对路径）。"""
    return Path(__file__).resolve().parent.parent


def _resource_root() -> Path:
    """只读资源根目录。

    - 源码运行：项目根目录
    - PyInstaller 打包后：解包目录 sys._MEIPASS
    """
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        return Path(getattr(sys, "_MEIPASS"))
    return _server_dir().parent


def _writable_root() -> Path:
    """可写数据根目录。

    - 源码运行：项目根目录
    - 打包后：可执行文件所在目录（_MEIPASS 是临时目录，重启即丢失，不能放数据）
    """
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return _server_dir().parent


SERVER_DIR = _server_dir()
RESOURCE_ROOT = _resource_root()
DATA_ROOT = _writable_root()


class Settings(BaseSettings):
    """应用配置，可通过环境变量覆盖（例如 IKAO_DEDUP_THRESHOLD=0.85）。"""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="IKAO_",
        extra="ignore",
    )

    app_name: str = "ikao"
    version: str = "1.0"
    api_prefix: str = "/api"

    # 可写数据目录：SQLite 库文件、导入的原始 JSON 都放这里
    data_dir: Path = DATA_ROOT / "data"
    # 留空则使用 sqlite:///data/ikao.db
    database_url: str = ""

    # 前端构建产物目录：存在时由后端直接托管（离线单机版）
    web_dist_dir: Path = RESOURCE_ROOT / "web" / "dist"

    # 导入去重阈值（0~1，越大越严格）
    dedup_threshold: float = 0.90
    # 单次导入允许的最大题目数，防止误传超大文件
    max_import_questions: int = 20000

    # 允许跨域的前端来源（开发期 vite dev server）
    cors_origins: List[str] = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:8010",
        "http://127.0.0.1:8010",
    ]

    @property
    def sqlalchemy_url(self) -> str:
        """SQLAlchemy 连接串。"""
        if self.database_url:
            return self.database_url
        self.data_dir.mkdir(parents=True, exist_ok=True)
        return f"sqlite:///{(self.data_dir / 'ikao.db').as_posix()}"


settings = Settings()
