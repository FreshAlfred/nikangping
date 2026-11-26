@echo off
rem =========================================================================
rem  一键装环境（分享给别人时先跑这个）
rem  需要：Windows 64 位 + Python 3.12（本项目不能用 3.13）
rem =========================================================================
setlocal
cd /d "%~dp0"

where py >nul 2>&1
if errorlevel 1 goto no_py
py -3.12 -V >nul 2>&1
if errorlevel 1 goto no_py

if exist ".venv\Scripts\python.exe" goto deps
echo [1/3] 创建 .venv ...
py -3.12 -m venv .venv
if errorlevel 1 goto venv_fail

:deps
echo [2/3] 安装 requirements.txt（首次约 1.5-2GB，按网速 10-30 分钟）...
".\.venv\Scripts\python.exe" -m pip install --upgrade pip
".\.venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 goto deps_fail

echo.
echo [3/3] 完成。
echo   有 NVIDIA 显卡（可选，约 2.5GB）: tools\setup_cuda_torch.bat
echo   启动: start.bat  （会自动申请管理员权限；游戏也要用管理员运行）
pause
exit /b 0

:no_py
echo [ERR] 没找到 Python 3.12。
echo   先装: https://www.python.org/downloads/release/python-31210/
echo   （不要用 3.13：rapidocr-onnxruntime 不支持）
pause
exit /b 1

:venv_fail
echo [ERR] .venv 创建失败
pause
exit /b 1

:deps_fail
echo [ERR] 依赖安装失败，看上面的报错；换国内源可试:
echo   .\.venv\Scripts\python.exe -m pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
pause
exit /b 1
