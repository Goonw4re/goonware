@echo off
chcp 65001 >nul
title GOONWARE
mode con: cols=90 lines=30
color 0D 
setlocal enabledelayedexpansion

:: Set script directory
set "SCRIPT_DIR=%~dp0"
cd /d "%SCRIPT_DIR%"

:: Function to print a fancy header
echo ==================================================
echo                    [ GOONWARE ]
echo ==================================================
echo.

:: Create necessary directories
for %%D in (assets assets\logs assets\resources assets\resources\img assets\resources\vid models) do (
    if not exist "%%D" mkdir "%%D"
)

:: Check if first run flag exists
if not exist "assets\first_run.flag" (
    echo [*] First time setup detected...
    
    :: Check Python installation
    python --version >nul 2>&1
    if errorlevel 1 (
        color 0C
        echo [!] Python is not installed! Please install Python 3.8 or later.
        pause
        exit /b 1
    )
    color 0D 

    :: Create virtual environment
    echo [+] Creating virtual environment...
    python -m venv venv
    if errorlevel 1 (
        color 0C
        echo [!] Failed to create virtual environment!
        pause
        exit /b 1
    )
    color 0D 

    :: Activate and install dependencies
    call venv\Scripts\activate.bat
    echo [+] Installing dependencies...
    pip install -r assets/requirements.txt
    if errorlevel 1 ('
        color 0C
        echo [!] Failed to install dependencies!
        pause
        exit /b 1
    )
    color 0D 

    :: Create first run flag
    echo. > assets\first_run.flag
) else (
    echo [+] Virtual environment detected. Activating...
    call venv\Scripts\activate.bat
)
color 0D 

:: Check if another instance is running
pythonw src/main.py --check-instance
if errorlevel 1 (
    color 0D 
    echo [+] No running instance detected. Starting GOONWARE...
    start /B pythonw src/main.py
    echo [✓] Showing GOONWARE UI.
) else (
    color 0D 
    echo [+] Existing instance found. Opening Config UI...
    start /B pythonw src/main.py --show-ui
    echo [✓] Showing existing GOONWARE UI.
)

timeout /t 2 /nobreak >nul
exit /b 0
