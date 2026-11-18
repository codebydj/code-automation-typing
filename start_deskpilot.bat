@echo off
setlocal
title DeskPilot - Setup & Launcher
cd /d "%~dp0"

echo ================================================================
echo                    DeskPilot Launcher
echo ================================================================
echo.

:: 1. Check Python installation
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python is not installed or not in your system PATH!
    echo.
    echo Please download and install Python 3.10, 3.11, or 3.12 from:
    echo   https://www.python.org/downloads/
    echo.
    echo IMPORTANT: During Python installation, be sure to check:
    echo   [x] "Add python.exe to PATH"
    echo.
    pause
    exit /b 1
)

echo [1/3] Python detected:
python --version
echo.

:: 2. Check / Create Virtual Environment
if not exist "venv" (
    echo [2/3] Creating Python virtual environment (venv)...
    python -m venv venv
    if %errorlevel% neq 0 (
        echo [ERROR] Failed to create virtual environment.
        pause
        exit /b 1
    )
    echo Virtual environment created successfully.
) else (
    echo [2/3] Existing virtual environment found.
)

:: 3. Activate Virtual Environment & Install Dependencies
call venv\Scripts\activate.bat

echo.
echo [3/3] Checking and installing dependencies from requirements.txt...
pip install -r requirements.txt --quiet
if %errorlevel% neq 0 (
    echo [WARNING] Retrying dependency installation with verbose output...
    pip install -r requirements.txt
)

echo.
echo ================================================================
echo               Launching DeskPilot...
echo ================================================================
echo.
python main.py

if %errorlevel% neq 0 (
    echo.
    echo [NOTICE] DeskPilot closed or encountered an issue.
    pause
)
