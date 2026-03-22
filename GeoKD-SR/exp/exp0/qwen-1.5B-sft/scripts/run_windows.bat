@echo off
REM Qwen2.5-1.5B SFT Training Script for Windows 6GB
REM Usage: run_windows.bat [splits|split_coords] [seed]

setlocal enabledelayedexpansion

REM 默认参数
set DATASET=splits
set SEED=42

REM 解析命令行参数
if not "%1"=="" set DATASET=%1
if not "%2"=="" set SEED=%2

echo ========================================
echo Qwen2.5-1.5B SFT Training (Windows 6GB)
echo ========================================
echo Dataset: %DATASET%
echo Seed: %SEED%
echo ========================================

REM 设置项目根目录
set PROJECT_ROOT=D:\30_keyan\GeoKD-SR
cd /d %PROJECT_ROOT%\exp\exp0\qwen-1.5B-sft

REM 检查 Python 环境
python --version >nul 2>&1
if errorlevel 1 (
    echo Error: Python not found. Please install Python 3.9+
    exit /b 1
)

REM 检查 GPU
python -c "import torch; print(f'CUDA available: {torch.cuda.is_available()}'); print(f'GPU: {torch.cuda.get_device_name(0) if torch.cuda.is_available() else \"None\"}')" 2>nul

REM 运行训练
echo.
echo Starting training...
python scripts/train.py ^
    --config configs/train_6gb.yaml ^
    --dataset %DATASET% ^
    --seed %SEED%

if errorlevel 1 (
    echo.
    echo Training failed with error code %errorlevel%
    exit /b %errorlevel%
)

echo.
echo ========================================
echo Training completed successfully!
echo ========================================

endlocal
