# -*- coding: utf-8 -*-
# SPDX-FileCopyrightText: 2026 梁小军 (GitHub: Jun-Leon)
# SPDX-License-Identifier: MIT
"""著作权信息单一数据源（Single Source of Truth）。

项目中所有对外可见的署名——接口响应、HTTP 响应头、打包产物文件属性、
启动横幅——统一从本模块取值，避免多处硬编码导致署名不一致。
"""

from __future__ import annotations

__all__ = [
    "AUTHOR_NAME",
    "GITHUB_HANDLE",
    "SOFTWARE_NAME",
    "SOFTWARE_NAME_EN",
    "VERSION",
    "COPYRIGHT_LINE",
    "SPDX_LICENSE",
    "REPOSITORY",
    "POWERED_BY",
]

# ---- 著作权主体 ----
AUTHOR_NAME = "梁小军"          # 真实姓名（软件著作权申请人）
GITHUB_HANDLE = "Jun-Leon"     # GitHub 昵称

# ---- 软件标识 ----
SOFTWARE_NAME = "ikao刷题平台软件"
SOFTWARE_NAME_EN = "ikao"
VERSION = "1.0"

# ---- 版权 / 许可 ----
COPYRIGHT_LINE = f"Copyright (c) 2026 {AUTHOR_NAME} (GitHub: {GITHUB_HANDLE})"
SPDX_LICENSE = "MIT"
REPOSITORY = "https://github.com/Jun-Leon/ikao"

# ---- 对外响应标识 ----
# HTTP 响应头只接受 latin-1 字符，故此处保持纯 ASCII；
# 中文署名通过 /api/meta 的 JSON 字段（author / copyright）下发。
POWERED_BY = f"{SOFTWARE_NAME_EN}/{VERSION} ({GITHUB_HANDLE})"
