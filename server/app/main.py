# -*- coding: utf-8 -*-
# SPDX-FileCopyrightText: 2026 梁小军 (GitHub: Jun-Leon)
# SPDX-License-Identifier: MIT
"""FastAPI 应用入口。

- 开发模式：后端只提供 /api/*，前端用 vite dev server（端口 5173）联调
- 单机模式：前端 build 产物放在 web/dist，后端直接托管，打开即用
"""

from __future__ import annotations

import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from .about import POWERED_BY, SOFTWARE_NAME
from .config import settings
from .database import init_db
from .routers import imports, meta, practice, profiles, questions, stats

WEB_DIST = settings.web_dist_dir
INDEX_HTML = WEB_DIST / "index.html"

app = FastAPI(
    title=SOFTWARE_NAME,
    version=settings.version,
    description=f"离线单机刷题工具后端 API · {POWERED_BY}",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def _add_signature_header(request, call_next):
    """为所有响应附加署名响应头，便于溯源构建产物。"""
    response = await call_next(request)
    response.headers["X-Powered-By"] = POWERED_BY
    return response


@app.on_event("startup")
def _on_startup() -> None:
    """启动即建表。"""
    init_db()


# ------------------------------------------------------------------ API 路由
app.include_router(meta.router, prefix=settings.api_prefix)
app.include_router(imports.router, prefix=settings.api_prefix)
app.include_router(profiles.router, prefix=settings.api_prefix)
app.include_router(questions.router, prefix=settings.api_prefix)
app.include_router(practice.router, prefix=settings.api_prefix)
app.include_router(stats.router, prefix=settings.api_prefix)


# ------------------------------------------------------------------ 前端托管
if (WEB_DIST / "assets").is_dir():
    app.mount("/assets", StaticFiles(directory=WEB_DIST / "assets"), name="assets")


@app.get("/", include_in_schema=False)
def index():
    if INDEX_HTML.is_file():
        return FileResponse(INDEX_HTML)
    return JSONResponse(
        {
            "message": "后端已启动，但未找到前端构建产物。",
            "hint": "开发模式请访问 http://localhost:5173；或先在 web/ 目录执行 npm run build",
            "api_docs": "/docs",
        }
    )


@app.get("/{full_path:path}", include_in_schema=False)
def spa_fallback(full_path: str):
    """非 API 路径统一交给前端路由处理。"""
    if full_path.startswith(settings.api_prefix.strip("/")):
        raise HTTPException(status_code=404, detail="接口不存在")
    if INDEX_HTML.is_file():
        candidate = WEB_DIST / full_path
        if full_path and candidate.is_file():
            return FileResponse(candidate)
        return FileResponse(INDEX_HTML)
    raise HTTPException(status_code=404, detail="前端未构建")


if __name__ == "__main__":
    # 默认 8010：8000 常被其他项目占用；可用 IKAO_PORT 环境变量覆盖
    import os

    uvicorn.run(
        "app.main:app",
        host="127.0.0.1",
        port=int(os.environ.get("IKAO_PORT", "8010")),
        reload=False,
    )
