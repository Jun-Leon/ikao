# -*- coding: utf-8 -*-
"""ikao 桌面启动器（PyInstaller 打包入口）。

职责：
1. 首次启动时，若题库为空，自动导入内置题库；
2. 自动挑选可用端口（默认 8010，被占用则依次后移）；
3. 启动本地服务并自动打开浏览器。

打包后即为 ikao.exe；开发期也可直接 `python packaging/launcher.py` 运行。
"""

from __future__ import annotations

import os
import socket
import sys
import threading
import time
import webbrowser
from pathlib import Path
from typing import Optional

APP_TITLE = "ikao 刷题平台"
PREFERRED_PORT = 8010
PORT_SCAN = 10  # 从 8010 起最多尝试 10 个端口
SEED_NAMES = ("seed_questions.json",)


# 源码方式直接运行本文件时，把 server/ 加入模块搜索路径（打包后该目录不存在，自动跳过）
_SRC_SERVER = Path(__file__).resolve().parent.parent / "server"
if _SRC_SERVER.is_dir() and str(_SRC_SERVER) not in sys.path:
    sys.path.insert(0, str(_SRC_SERVER))


def _writable_root() -> Path:
    """可写根目录：打包后为 exe 所在目录，源码运行为项目根目录。"""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent.parent


def _find_seed() -> Optional[Path]:
    """定位内置题库文件：优先 exe 同级 data/，其次打包解包目录。"""
    root = _writable_root()
    for name in SEED_NAMES:
        candidate = root / "data" / name
        if candidate.is_file():
            return candidate
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        for name in SEED_NAMES:
            candidate = Path(meipass) / "data" / name
            if candidate.is_file():
                return candidate
    return None


def _pick_port(preferred: int) -> int:
    """返回第一个可绑定的端口。"""
    for port in range(preferred, preferred + PORT_SCAN):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                sock.bind(("127.0.0.1", port))
                return port
            except OSError:
                continue
    raise SystemExit(
        f"[错误] 端口 {preferred}~{preferred + PORT_SCAN - 1} 均被占用，请关闭占用程序后重试。"
    )


def _seed_database() -> None:
    """题库为空时导入内置题库（在服务启动前执行）。"""
    from sqlalchemy import func, select

    from app.database import SessionLocal, init_db
    from app.models import Question
    from app.services.import_service import ImportService

    init_db()
    db = SessionLocal()
    try:
        count = int(db.scalar(select(func.count(Question.id))) or 0)
        if count > 0:
            print(f"[题库] 当前已有 {count} 道题，跳过内置题库导入。")
            return
        seed = _find_seed()
        if seed is None:
            print("[题库] 未找到内置题库文件，本次将启动为空题库（可在「题库导入」页面自行导入）。")
            return
        print(f"[题库] 首次启动，正在导入内置题库 {seed.name}，请稍候 ...")
        log = ImportService(db).import_text(
            seed.read_text(encoding="utf-8"), source_name=seed.name, threshold=None
        )
        print(
            f"[题库] 完成：解析 {log.total}，入库 {log.imported}，"
            f"重复 {log.duplicated}，失败 {log.failed}。"
        )
    finally:
        db.close()


def _open_browser_later(port: int) -> None:
    time.sleep(1.5)
    try:
        webbrowser.open(f"http://127.0.0.1:{port}/")
    except Exception:  # noqa: BLE001 浏览器打开失败不影响服务
        pass


def main() -> None:
    port = _pick_port(int(os.environ.get("IKAO_PORT", PREFERRED_PORT)))

    print("=" * 62)
    print(f"  {APP_TITLE}  正在启动，请稍候 ...")
    print("=" * 62)

    _seed_database()

    import uvicorn

    from app.main import app

    print("-" * 62)
    print(f"  访问地址：http://127.0.0.1:{port}/")
    print("  浏览器将自动打开；本窗口是服务进程，关闭窗口即退出程序。")
    print("-" * 62)

    threading.Thread(target=_open_browser_later, args=(port,), daemon=True).start()

    # 显式指定 h11 + asyncio + 关闭 ws：全部为纯 Python 实现，打包最稳、体积最小
    uvicorn.run(
        app,
        host="127.0.0.1",
        port=port,
        loop="asyncio",
        http="h11",
        ws="none",
        log_level="info",
    )


if __name__ == "__main__":
    main()
