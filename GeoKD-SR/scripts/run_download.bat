@echo off
chcp 65001 >nul
echo ========================================
echo   Qwen2.5 模型下载工具
echo ========================================
echo.

REM 切换到脚本所在目录
cd /d "%~dp0"

REM 检查Python环境
python --version >nul 2>&1
if errorlevel 1 (
    echo 错误: 未找到Python，请先安装Python 3.8+
    pause
    exit /b 1
)

echo Python版本:
python --version
echo.

REM 安装依赖
echo 检查并安装依赖...
pip install -q -r requirements.txt

echo.
echo 依赖安装完成！
echo.

REM 设置镜像加速（可选）
echo 是否使用国内镜像加速下载? (推荐)
echo 1. 使用 hf-mirror.com (国内快速)
echo 2. 使用官方源 huggingface.co
set /p mirror_choice="请选择 (1/2): "

if "%mirror_choice%"=="1" (
    set HF_ENDPOINT=https://hf-mirror.com
    echo 已设置镜像源: %HF_ENDPOINT%
) else (
    echo 使用官方源
)

echo.
echo ========================================
echo 开始下载模型...
echo ========================================
echo.

REM 运行下载脚本
python download_models.py

echo.
echo ========================================
echo 下载流程结束
echo ========================================
pause
