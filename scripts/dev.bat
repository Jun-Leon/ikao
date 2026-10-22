@echo off
rem ============================================================
rem  ikao 刷题平台 - 开发模式一键启动
rem  两个窗口：后端 8010（API）/ 前端 5173（页面）
rem  端口可用环境变量覆盖：IKAO_PORT / VITE_API_TARGET
rem ============================================================
setlocal
chcp 65001 >nul
cd /d "%~dp0.."
set "ROOT=%CD%"
if "%IKAO_PORT%"=="" set "IKAO_PORT=8010"

echo [提示] 首次运行请先完成依赖安装：
echo        后端：cd server ^&^& pip install -r requirements.txt
echo        前端：cd web ^&^& npm install
echo.

echo [1/2] 启动后端 http://127.0.0.1:%IKAO_PORT% ...
start "ikao-后端" cmd /k "cd /d "%ROOT%\server" && python -m uvicorn app.main:app --reload --host 127.0.0.1 --port %IKAO_PORT%"

echo [2/2] 启动前端 http://127.0.0.1:5173 ...
start "ikao-前端" cmd /k "cd /d "%ROOT%\web" && npm run dev"

echo.
echo 请在浏览器打开： http://127.0.0.1:5173
echo （API 文档： http://127.0.0.1:%IKAO_PORT%/docs ）
echo.
pause
