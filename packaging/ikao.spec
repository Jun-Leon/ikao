# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller 打包配置：生成免安装绿色版 ikao（onedir）。

构建方式（在项目根目录执行）：
    python -m PyInstaller packaging/ikao.spec --noconfirm --clean

产物：dist/ikao/ikao.exe 及其依赖目录。

要点：
- 前端构建产物 web/dist 打进包内，运行时由后端直接托管；
- 内置题库 data/seed_questions.json 打进包内，首次启动自动导入；
- 强制使用纯 Python 的 h11 + asyncio（见 launcher.py），故排除 httptools/uvloop 等编译件。
"""

from pathlib import Path

PACKAGING_DIR = Path(SPECPATH).resolve()
PROJECT_DIR = PACKAGING_DIR.parent
SERVER_DIR = PROJECT_DIR / "server"
WEB_DIST = PROJECT_DIR / "web" / "dist"
SEED_JSON = PROJECT_DIR / "data" / "seed_questions.json"
VERSION_INFO = PACKAGING_DIR / "version_info.txt"

if not WEB_DIST.is_dir():
    raise SystemExit(
        "未找到 web/dist，请先构建前端：cd web && npm run build"
    )

datas = [(str(WEB_DIST), "web/dist")]
if SEED_JSON.is_file():
    datas.append((str(SEED_JSON), "data"))
else:
    print(f"[spec] 警告：未找到内置题库 {SEED_JSON}，打出的包将为空题库。")

hiddenimports = [
    "uvicorn.logging",
    "uvicorn.loops.asyncio",
    "uvicorn.protocols.http.h11_impl",
    "uvicorn.lifespan.on",
    "openpyxl",
]

# 全部为纯 Python 运行时不需要的编译件/调试件，排除以缩小体积、避免打包踩坑
excludes = [
    "uvloop",
    "httptools",
    "websockets",
    "wsproto",
    "watchfiles",
    "pytest",
    "tkinter",
    "matplotlib",
    "numpy",
    "pandas",
    "IPython",
]

a = Analysis(
    [str(PACKAGING_DIR / "launcher.py")],
    pathex=[str(SERVER_DIR)],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=excludes,
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="ikao",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,
    version=str(VERSION_INFO) if VERSION_INFO.is_file() else None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    name="ikao",
)
