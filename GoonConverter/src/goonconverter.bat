@echo off
chcp 65001 >nul
title GOONWARE Converter
color 0D
setlocal enabledelayedexpansion

:: Set script directory and navigate to project root
set "SRC_DIR=%~dp0"
set "CONVERTER_DIR=%SRC_DIR%\.."
set "PROJECT_ROOT=%CONVERTER_DIR%\.."
cd /d "%PROJECT_ROOT%"

:: Function to print a fancy header
echo ==================================================
echo              [ GOONWARE CONVERTER ]
echo ==================================================
echo.

:: Check Python installation
python --version >nul 2>&1
if errorlevel 1 (
    color 0C
    echo [!] Python is not installed! Please install Python 3.8 or later.
    pause
    exit /b 1
)
color 0D 

:: Check if virtual environment exists
if not exist "venv" (
    echo [!] Virtual environment not found! Please run start.bat first.
    pause
    exit /b 1
)

:: Activate virtual environment
call venv\Scripts\activate.bat

:: Launch the converter UI
echo [+] Launching GOONWARE Model Converter...
start /B pythonw -m GoonConverter.src.launcher

:: Wait for 1 seconds and then close the command prompt
timeout /t 1 /nobreak >nul
exit /b 0 